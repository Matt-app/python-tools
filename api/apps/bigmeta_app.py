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