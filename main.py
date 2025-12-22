# -*- coding: utf-8 -*-
"""
基于动态拦截 + AST 回退的 SQL 提取工具。

核心能力：
- 动态拦截 job.base.ClientUtil.execSql(sql, locals())，直接捕获渲染后的 SQL。
- 若动态执行失败或未捕获到 SQL，则使用 AST 静态解析提取 SQL 模板并进行占位符替换。
- 额外支持 $name$ 风格占位符，用传入变量字典进行替换。

使用方式：
  python sql_extractor.py --root <扫描目录> --bizDate 20240131 --output-dir <输出目录>
  python sql_extractor.py --root . --pattern fra_due_diligence_contact.py
  python sql_extractor.py --root . --extra-var key=value --extra-var another=val

说明：
- 该脚本不会连接数据库，也不会真正执行 SQL，仅做收集与写出。
- 输出文件命名：<源文件名去后缀>.sql。
"""

import argparse, ast, re, datetime as dt, sys, types, runpy, json
from pathlib import Path
from copy import copy

# {key} 占位符匹配（避免嵌套花括号）
BRACE_RE = re.compile(r"\{([^{}]+)\}")
DOLLAR_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)\$")
DOLLAR_BRACE_RE = re.compile(r"\$\{([^{}]+)\}")
# 动态拦截阶段用于暂存已捕获的 SQL
_captured_sqls = []


# ================== 公共工具函数 ==================

def to_yyyymmdd(s):
    """将输入日期字符串转换为 yyyymmdd 格式；若无法识别则原样返回。"""
    s = str(s).strip()
    for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y%m%d")
        except:
            pass
    return s


def to_yyyy_mm_dd(s):
    """将输入日期字符串转换为 yyyy-mm-dd 格式；若无法识别则原样返回。"""
    s = str(s).strip()
    for fmt in ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except:
            pass
    return s


def sub_placeholders(tpl, mapping):
    """使用正则将模板中的 {key} 用 mapping[key] 替换，缺失则保留原样。"""

    def repl(m):
        k = m.group(1).strip()
        v = mapping.get(k)
        return str(v) if v is not None else "{" + k + "}"

    return BRACE_RE.sub(repl, str(tpl))


def sub_dollar_placeholders(text, mapping):
    """将文本中的 $name$ 替换为 mapping[name]；若缺失则保留原样。"""

    def repl(m):
        k = m.group(1)
        if k in mapping and mapping[k] is not None:
            return str(mapping[k])
        return m.group(0)

    return DOLLAR_RE.sub(repl, str(text))


def sub_dollar_brace_placeholders(text, mapping):
    """将文本中的 ${name} 替换为 mapping[name]；若缺失则保留原样。"""

    def repl(m):
        k = m.group(1).strip()
        v = mapping.get(k)
        return str(v) if v is not None else m.group(0)

    return DOLLAR_BRACE_RE.sub(repl, str(text))


def ensure_semicolon(sql_text: str) -> str:
    """确保每条 SQL 末尾带分号。"""
    s = (sql_text or "").strip()
    if not s:
        return s
    return s if s.endswith(';') else s + ';'


# ================== 动态拦截模块 ==================

class _StubExit(Exception):
    """用来替换 util.exit/系统退出的轻量异常，避免终止当前进程。"""
    pass


def install_stub_modules():
    """安装并注册桩模块到 sys.modules，用于拦截目标脚本依赖。
    - 构造包结构：job、job.base
    - 提供 job.base.Joabase.ExitCode
    - 提供 job.base.ClientUtil：execSql/exit/DateUtils 等必要符号
    """
    global _captured_sqls
    _captured_sqls.clear()

    # 1) 创建包结构，标记 __path__ 使其作为包被 import
    job_pkg = types.ModuleType("job")
    job_pkg.__path__ = []
    job_base_pkg = types.ModuleType("job.base")
    job_base_pkg.__path__ = []

    # 2) Joabase.ExitCode（部分脚本在退出时会引用）
    class ExitCode:
        EXIT_ERROR = 1
        EXIT_SUCCESS = 0

    joa_mod = types.ModuleType("job.base.Joabase")
    joa_mod.ExitCode = ExitCode

    # 3) ClientUtil 所需工具：DateUtils + execSql/exit 等
    class DateUtils:
        """提供日期格式化方法，与业务脚本保持一致接口。"""

        @staticmethod
        def getShortDate(bizDate):
            return to_yyyymmdd(bizDate)

        @staticmethod
        def getLongDate(bizDate):
            return to_yyyy_mm_dd(bizDate)

    def execSql(sql, mapping=None):
        """拦截 util.execSql：仅记录 SQL，不做任何数据库操作。
        - sql: 字符串模板或渲染后字符串
        - mapping: 通常传入 locals()，用于占位符替换
        """
        global _captured_sqls
        rendered = str(sql)
        if mapping:
            # 先尝试 str.format(**mapping)，失败则回退为正则替换
            try:
                rendered = rendered.format(**mapping)
            except:
                rendered = sub_placeholders(rendered, mapping)
            # 处理 $name$ 与 ${name} 风格占位符
            rendered = sub_dollar_placeholders(rendered, mapping)
            rendered = sub_dollar_brace_placeholders(rendered, mapping)
        _captured_sqls.append(rendered)

    def exit(code, msg):
        """拦截 util.exit：改为抛出轻量异常，防止退出当前进程。"""
        raise _StubExit(f"code={code}, msg={msg}")

    # ---- 额外拦截的 ClientUtil 常用方法（动态生成 SQL 并转调 execSql 以记录）----
    class DepException(Exception):
        pass

    class Config:
        EXCEPTION_INCR_DATA = 'EXCEPTION_INCR_DATA'

    def dropTable(tableName):
        sql = "DROP TABLE IF EXISTS %s" % (tableName)
        execSql(sql)

    def addPartition(tableName, bitDate, partitionKey='DT'):
        # 统一为分区值加引号，避免语法歧义
        sql = "ALTER TABLE %s ADD IF NOT EXISTS PARTITION(%s='%s')" % (tableName, partitionKey, bitDate)
        execSql(sql)

    def cloneTable(srcTable, destTable, hasPartition=True):
        if hasPartition:
            sql = "CREATE TABLE IF NOT EXISTS %s LIKE %s" % (destTable, srcTable)
        else:
            sql = "CREATE TABLE IF NOT EXISTS %s AS SELECT * FROM %s LIMIT 0" % (destTable, srcTable)
        execSql(sql)

    def incrDataArch(srcTable, destTable, bitDate):
        cloneTable(srcTable, destTable)
        # 若上一步标记了错误则中断
        if getattr(util_mod, '_ERRORCODE', 0):
            return
        addPartition(destTable, bitDate)
        if not getattr(util_mod, '_ERRORCODE', 0):
            sql = "INSERT OVERWRITE %s PARTITION(DT) SELECT * FROM %s WHERE DT='%s'" % (destTable, srcTable, bitDate)
            execSql(sql)

    def incrDataArchEx(srcTable, destTable, bitDate):
        incrDataArch(srcTable, destTable, bitDate)
        if getattr(util_mod, '_ERRORCODE', 0):
            raise DepException(Config.EXCEPTION_INCR_DATA)

    def fullDataArch(srcTable, destTable, bitDate):
        cloneTable(srcTable, destTable, False)
        if getattr(util_mod, '_ERRORCODE', 0):
            return
        sql = "INSERT OVERWRITE %s SELECT * FROM %s WHERE DT='%s'" % (destTable, srcTable, bitDate)
        execSql(sql)

    util_mod = types.ModuleType("job.base.ClientUtil")
    util_mod.DateUtils = DateUtils
    util_mod.execSql = execSql
    util_mod.exit = exit
    util_mod.ERRORCODE = 0
    util_mod._ERRORCODE = 0
    util_mod.DepException = DepException
    util_mod.Config = Config
    # 暴露新增方法
    util_mod.dropTable = dropTable
    util_mod.addPartition = addPartition
    util_mod.cloneTable = cloneTable
    util_mod.incrDataArch = incrDataArch
    util_mod.incrDataArchEx = incrDataArchEx
    util_mod.fullDataArch = fullDataArch
    # 业务中可能调用的其他函数，占位为 no-op，避免 AttributeError
    util_mod.debug = util_mod.checkArgsEx = util_mod.computeState = util_mod.destroy = lambda *a, **k: None

    # 4) 一次性注册到 sys.modules，并把属性挂到父包，保证 from job.base import ClientUtil 可用
    sys.modules.update({
        "job": job_pkg,
        "job.base": job_base_pkg,
        "job.base.Joabase": joa_mod,
        "job.base.ClientUtil": util_mod,
    })
    setattr(job_base_pkg, "Joabase", joa_mod)
    setattr(job_base_pkg, "ClientUtil", util_mod)


def run_script_with_dynamic_intercept(py_file, bizDate):
    """用桩模块运行目标脚本：
    - 设置 sys.argv = [脚本路径, bizDate]
    - 以 __main__ 模式执行目标脚本（可能触发 util.execSql）
    - 执行结束后恢复 sys.argv 和 sys.modules
    返回: (success: bool, captured_sqls: List[str])
    """
    global _captured_sqls
    original_argv = sys.argv[:]
    original_modules = dict(sys.modules)

    try:
        install_stub_modules()
        sys.argv = [str(py_file), bizDate]
        runpy.run_path(str(py_file), run_name="__main__")
        success = True
    except (_StubExit, SystemExit):
        # 业务脚本主动退出也视为成功（我们已经拿到 SQL）
        success = True
    except:
        # 运行失败，交由 AST 回退处理
        success = False
    finally:
        # 完整恢复现场（argv + modules）
        sys.argv[:] = original_argv
        for key in list(sys.modules.keys()):
            if key not in original_modules:
                del sys.modules[key]
        sys.modules.update(original_modules)

    return success, _captured_sqls[:]


# ================== AST 回退模块 ==================

def joinedstr_to_template(js):
    """将 f-string 的 AST 结点还原为包含 {name} 占位的模板字符串。"""
    parts = []
    for v in js.values:
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            parts.append(v.value)
        elif isinstance(v, ast.FormattedValue):
            if isinstance(v.value, ast.Name):
                parts.append("{" + v.value.id + "}")
            else:
                # 复杂表达式尽量转源码；失败则以 {expr} 占位
                try:
                    parts.append("{" + ast.unparse(v.value) + "}")
                except:
                    parts.append("{expr}")
        else:
            parts.append("")
    return "".join(parts)


def collect_assign_strings(tree):
    """收集形如 x = "..." 或 x = f"..." 的字符串赋值，返回 {变量名: 模板}。"""
    assigns = {}
    for n in ast.walk(tree):
        if (
                isinstance(n, ast.Assign)
                and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
        ):
            name, val = n.targets[0].id, n.value
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                assigns[name] = val.value
            elif isinstance(val, ast.JoinedStr):
                assigns[name] = joinedstr_to_template(val)
    return assigns


def find_execsql_calls(tree):
    """定位 ..execSql(...) 的调用，返回列表 [(node, 变量名或 None, 字面量或 None)]。"""
    calls = []
    for n in ast.walk(tree):
        if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "execSql"
                and n.args
        ):
            arg0 = n.args[0]
            sql_name = sql_lit = None
            if isinstance(arg0, ast.Name):
                sql_name = arg0.id
            elif isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                sql_lit = arg0.value
            elif isinstance(arg0, ast.JoinedStr):
                sql_lit = joinedstr_to_template(arg0)
            calls.append((n, sql_name, sql_lit))
    return calls


def _value_to_template(node):
    """将 AST 节点转换为字符串模板。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return joinedstr_to_template(node)
    return None


def _traverse_block(stmts, assigns, out_tpls):
    """顺序遍历语句块，维护最近一次的字符串赋值，遇到 execSql 则取就近模板。"""
    for stmt in stmts:
        # 赋值语句：只跟踪 x = "..." / x = f"..."
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            tpl = _value_to_template(stmt.value)
            if tpl is not None:
                assigns[stmt.targets[0].id] = tpl
        # 表达式调用：查找 execSql
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'execSql' and call.args:
                arg0 = call.args[0]
                tpl = None
                if isinstance(arg0, ast.Name):
                    tpl = assigns.get(arg0.id)
                else:
                    tpl = _value_to_template(arg0)
                if tpl is not None:
                    out_tpls.append(tpl)
        # 复合语句块：递归，使用 assigns 的浅拷贝隔离分支
        if isinstance(stmt, (ast.If, ast.For, ast.While, ast.With, ast.AsyncWith, ast.Try)):
            if isinstance(stmt, ast.If):
                _traverse_block(stmt.body, copy(assigns), out_tpls)
                _traverse_block(stmt.orelse, copy(assigns), out_tpls)
            elif isinstance(stmt, (ast.For, ast.While)):
                _traverse_block(stmt.body, copy(assigns), out_tpls)
                _traverse_block(stmt.orelse, copy(assigns), out_tpls)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                _traverse_block(stmt.body, copy(assigns), out_tpls)
            elif isinstance(stmt, ast.Try):
                _traverse_block(stmt.body, copy(assigns), out_tpls)
                for h in stmt.handlers:
                    _traverse_block(h.body, copy(assigns), out_tpls)
                _traverse_block(stmt.orelse, copy(assigns), out_tpls)
                _traverse_block(stmt.finalbody, copy(assigns), out_tpls)
        # 函数/类定义：独立作用域
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _traverse_block(getattr(stmt, 'body', []), {}, out_tpls)


def find_execsql_templates_ordered(tree):
    """按源码顺序提取 execSql 调用对应的 SQL 模板。"""
    templates = []
    module_body = tree.body if isinstance(tree, ast.Module) else []
    _traverse_block(module_body, {}, templates)
    return templates


def extract_sql_with_ast_fallback(py_file, base_vars):
    """AST 回退机制：静态解析提取 SQL 模板并进行占位符替换。
    返回: List[str] - 渲染后的 SQL 列表
    """
    try:
        src = py_file.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(src, filename=str(py_file))
        templates = find_execsql_templates_ordered(tree)

        # 兼容旧逻辑（若未定义按序方法则退回原 find_execsql_calls 收集策略）
        if not templates:
            assigns = collect_assign_strings(tree)
            calls = find_execsql_calls(tree)
            for _, name, lit in calls:
                tpl = lit if lit is not None else assigns.get(name)
                if tpl:
                    templates.append(tpl)

        results = []
        for tpl in templates:
            rendered = sub_placeholders(tpl, base_vars)
            rendered = sub_dollar_placeholders(rendered, base_vars)
            rendered = sub_dollar_brace_placeholders(rendered, base_vars)
            results.append(rendered)
        return results
    except:
        return []


# ================== 文件处理和主程序模块 ==================

def extract_sql_from_file(py_file, base_vars):
    """从单个 .py 文件中提取 SQL：
    1) 优先动态拦截（若目标脚本会执行到 util.execSql）
    2) 失败则回退 AST 解析（提取模板并用 base_vars 替换占位符）
    返回 (pairs, mode)：
      - pairs: [(原模板或动态结果, 渲染结果)]
      - mode: 'dynamic' | 'ast' | 'none'
    """
    # 1) 动态拦截优先
    ok, dyn_sqls = run_script_with_dynamic_intercept(py_file, base_vars.get('bizDate', ''))
    if ok and dyn_sqls:
        # 动态捕获已经是最终渲染结果
        return ([(s, s) for s in dyn_sqls], 'dynamic')

    # 2) AST 回退
    ast_sqls = extract_sql_with_ast_fallback(py_file, base_vars)
    if ast_sqls:
        return ([(s, s) for s in ast_sqls], 'ast')

    return ([], 'none')


def main():
    """命令行入口：遍历 root 下的 Python 文件，提取 SQL 并写出到 output-dir。"""
    parser = argparse.ArgumentParser(description='提取 util.execSql SQL 语句')
    parser.add_argument('--root', default=str(Path.cwd()), help='扫描根目录')
    parser.add_argument('--bizDate', default=dt.date.today().strftime('%Y%m%d'), help='业务日期，默认今天')
    parser.add_argument('--output-dir', help='输出目录，默认 <root>/extracted_sql')
    parser.add_argument('--pattern', default='*.py', help='文件匹配模式（glob）')
    parser.add_argument('--extra-var', action='append', default=[], help='额外占位符变量，格式 key=value，可多次')
    parser.add_argument('--files', action='append', default=[], help='指定要处理的 .py 文件路径，可多次')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出渲染后的 SQL 到标准输出（不写入文件）')
    args = parser.parse_args()

    # 目录与输出目录
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f'[ERROR] 目录不存在: {root}')
        return 2

    # JSON 模式下不写文件；非 JSON 模式才创建输出目录
    output_dir = None
    if not args.json:
        output_dir = Path(args.output_dir).resolve() if args.output_dir else root / 'extracted_sql'
        output_dir.mkdir(parents=True, exist_ok=True)

    # 变量映射（可被脚本中的 {bizDate}/{bizDate_short}/{bizDate10} 等占位使用）
    variables = {
        'bizDate': args.bizDate,
        'bizDate_short': to_yyyymmdd(args.bizDate),
        'bizDate10': to_yyyy_mm_dd(args.bizDate)
    }
    for kv in args.extra_var:
        if '=' in kv:
            k, v = kv.split('=', 1)
            variables[k.strip()] = v.strip()

    # 收集候选文件（优先使用 --files 指定的文件；否则按 pattern 搜索，且排除自身）
    files = []
    if args.files:
        for f in args.files:
            p = Path(f).resolve()
            if p.is_file() and p.name.endswith('.py'):
                files.append(p)
    else:
        files = [f for f in root.rglob(args.pattern)
                 if f.is_file() and f.name.endswith('.py') and f.name != 'sql_extractor.py']

    # 逐文件提取并输出；JSON 模式下仅收集结果并在末尾一次性打印
    summary = []
    results_json = []
    for py_file in sorted(files):
        try:
            pairs, mode = extract_sql_from_file(py_file, variables)
            if not pairs:
                if not args.json:
                    print(f'[WARN] 未找到 SQL: {py_file}')
                continue

            # 组合为单一 SQL 文本，每段以分号结尾，中间以空行分隔
            stmts = [ensure_semicolon(rendered.strip()) for (_raw, rendered) in pairs]
            combined_sql = "\n\n".join(stmts)

            if not args.json:
                output_file = output_dir / f'{py_file.stem}.sql'
                output_file.write_text(combined_sql, encoding='utf-8')
                summary.append(f'{py_file.name} -> {output_file.name}')
                mode_cn = '动态拦截' if mode == 'dynamic' else ('AST回退' if mode == 'ast' else '未知')
                print(f'[OK] {py_file} -> {output_file}  (方式: {mode_cn})')

            # JSON 按文件聚合返回
            results_json.append({
                'file': str(py_file),
                'count': len(stmts),
                'rendered_sql': combined_sql,
                'mode': mode
            })
        except Exception as e:
            if not args.json:
                print(f'[ERR] 处理失败 {py_file}: {e}')

    if args.json:
        # 仅输出 JSON，不混杂其他日志，便于上游程序解析
        print(json.dumps(results_json, ensure_ascii=False))
        return 0

    # 非 JSON 模式下输出汇总
    if summary:
        print('\n[SUMMARY] 输出 SQL 文件:')
        for s in summary:
            print(f'  {s}')
    else:
        print('[SUMMARY] 未输出任何 SQL')

    return 0


if __name__ == '__main__':
    sys.exit(main())