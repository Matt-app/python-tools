from flask import jsonify


@manager.route('/demo', methods=['GET'])  # noqa: F821
def demo_api():
    """示例接口
    ---
    tags:
      - 示例模块
      - http://127.0.0.1:8888/v1/test/demo
    responses:
      200:
        description: 返回成功消息
        examples:
          application/json: {"message": "success"}
    """
    return {"message": "success"}


@manager.route('/echo', methods=['POST'])  # noqa: F821
def echo_api():
    """回声测试接口
    ---
    tags:
      - 示例模块
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            text:
              type: string
    responses:
      200:
        description: 返回输入内容
    """
    from flask import request
    return jsonify({"echo": request.json.get("text")})


# ======== SQL 解析接口（支持并发限制） ========
from threading import BoundedSemaphore
from api.conf.config import SQL_PARSE_MAX_CONCURRENCY
_sql_parse_sema = BoundedSemaphore(value=max(1, int(SQL_PARSE_MAX_CONCURRENCY)))


@manager.route('/sql/parse', methods=['POST'])  # noqa: F821
def sql_parse_api():
    """SQL 解析接口：将 SQL 文本解析为语法树（AST）
    ---
    tags:
      - SQL 工具
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            sql:
              type: string
              description: 待解析的 SQL 文本（可包含多条语句）
            dialect:
              type: string
              description: 可选，SQL 方言（如 mysql、postgres、hive、spark、trino 等）
    responses:
      200:
        description: 解析结果
    """
    from flask import request
    from api.utils.sql_parser import parse_sql_to_ast

    _sql_parse_sema.acquire()  # 超过并发时会等待
    try:
        data = request.json or {}
        sql = (data.get('sql') or '').strip()
        dialect = (data.get('dialect') or None)

        if not sql:
            return jsonify({"ok": False, "error": "sql is required", "statements": []}), 400

        result = parse_sql_to_ast(sql, dialect)
        status = 200 if result.get('ok') else 400
        return jsonify(result), status
    finally:
        _sql_parse_sema.release()


@manager.route('/python/parse', methods=['POST'])  # noqa: F821
def python_parse_api():
    """Python 语法解析接口：解析 Python2/3 源码，抽取 AST 概览及 PySpark/execute 调用中的 SQL。
    ---
    tags:
      - Python 工具
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            code:
              type: string
              description: 待解析的 Python 源码文本
            version_hint:
              type: string
              description: 可选，'py2' 或 'py3'，用于覆盖自动检测
            extract_ast:
              type: boolean
              description: 是否提取 AST 概览
            extract_sql:
              type: boolean
              description: 是否提取 SQL 调用
    responses:
      200:
        description: 解析结果
    """
    from flask import request
    from api.utils.py_parser import parse_python_script

    data = request.json or {}
    code = (data.get('code') or '').rstrip()
    version_hint = data.get('version_hint')
    extract_ast = bool(data.get('extract_ast', True))
    extract_sql = bool(data.get('extract_sql', True))

    if not code:
        return jsonify({"ok": False, "error": "code is required"}), 400

    result = parse_python_script(code, version_hint=version_hint, extract_ast=extract_ast, extract_sql=extract_sql)
    # 兼容字段别名：对外返回统一键名
    if isinstance(result, dict):
        if 'detected_version' in result and 'python_version' not in result:
            result['python_version'] = result.get('detected_version')
        if 'sql_queries' in result and 'sql_calls' not in result:
            result['sql_calls'] = result.get('sql_queries')
    status = 200 if result.get('ok') else 400
    return jsonify(result), status