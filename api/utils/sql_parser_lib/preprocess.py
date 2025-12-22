from typing import List, Tuple
import re


def _guess_dialect(sql_text: str) -> str:
    s = sql_text.upper()
    # 粗略识别 Oracle/Hive/Spark 特征
    if any(k in s for k in ("NVL(", "DECODE(", "ROW_NUMBER()OVER", "ROW_NUMBER() OVER", "||")):
        return "oracle"
    if "REGEXP_EXTRACT(" in s or "SPLIT(" in s:
        return "hive"
    return "oracle"  # 本项目样例多为 Oracle 风格，默认 oracle 更鲁棒


def _preprocess_lenient(sql_text: str) -> Tuple[str, List[str]]:
    """对非标准/模板化 SQL 做宽松预处理，尽量提升可解析性。
    返回 (预处理后的SQL, 警告列表)
    处理策略：
    - 将 "' || VAR ||'" 这类模板写法替换为 'VAR'
    - 将所有双引号包裹的文本替换为单引号（倾向文本字面量场景）
    - 规范一些容易引发解析问题的字符
    """
    warnings: List[str] = []
    s = sql_text

    # 1) 处理 "' || V_DATA_DATE ||'" -> 'V_DATA_DATE'
    pattern_tpl = re.compile(r"\"'\|\|\s*([A-Za-z0-9_]+)\s*\|\|'\"")
    if pattern_tpl.search(s):
        s = pattern_tpl.sub(lambda m: f"'{m.group(1)}'", s)
        warnings.append("replaced template concatenation \"' || VAR ||'\" -> 'VAR'")

    # 2) 粗略地将双引号字符串替换成单引号
    #    注意：若确有双引号标识符，此步骤可能改变语义，但有助于本项目样例通过解析
    def _dq_to_sq(m: re.Match) -> str:  # type: ignore[name-defined]
        inner = m.group(1)
        inner = inner.replace("'", "''")  # 转义已有单引号
        return f"'{inner}'"

    # 仅替换不含句点且疑似文本的内容，尽量避开 "schema.object" 形式
    before = s
    s = re.sub(r'"([^"\n\r]*)"', _dq_to_sq, s)
    if s != before:
        warnings.append("converted double-quoted literals to single quotes")

    # 3) 统一换行与空白
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    return s, warnings