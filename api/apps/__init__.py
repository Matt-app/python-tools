import os
import sys
import logging
import json
import traceback
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from flask import Blueprint, Flask, jsonify, request, g
from werkzeug.wrappers.request import Request
from werkzeug.exceptions import HTTPException

# Optional imports with graceful fallbacks
try:
    from flask_cors import CORS  # type: ignore
except Exception:  # pragma: no cover
    CORS = None  # type: ignore

try:
    from flasgger import Swagger  # type: ignore
except Exception:  # pragma: no cover
    Swagger = None  # type: ignore

try:
    from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer  # noqa: F401
except Exception:  # pragma: no cover
    Serializer = None  # type: ignore

# bigmeta_preprocess is optional; provide fallbacks
try:
    from bigmeta_preprocess.api.utils import CustomJSONEncoder as _CustomJSONEncoder  # type: ignore
    from bigmeta_preprocess.api.utils import commands as _commands  # type: ignore
    from flask_session import Session as _Session  # type: ignore
    from bigmeta_preprocess.api import settings as _settings  # noqa: F401
    from bigmeta_preprocess.api.utils.api_utils import server_error_response as _server_error_response  # type: ignore
    from bigmeta_preprocess.api.constants import API_VERSION as _API_VERSION  # type: ignore
except Exception:
    _CustomJSONEncoder = None
    _commands = None
    _Session = None
    _server_error_response = None
    _API_VERSION = None

# Fallbacks when optional deps are missing
class DefaultJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

def default_server_error_response(e):
    logging.exception("Unhandled server error: %s", e)
    return jsonify({
        "ok": False,
        "error": str(e),
        "trace": traceback.format_exc(limit=3)
    }), 500

API_VERSION = _API_VERSION or os.getenv("API_VERSION", "v1")
CustomJSONEncoder = _CustomJSONEncoder or DefaultJSONEncoder
server_error_response = _server_error_response or default_server_error_response
Session = _Session or (lambda app: None)

__all__ = ["app"]

Request.json = property(lambda self: self.get_json(force=True, silent=True))

app = Flask(__name__)

# Swagger is optional
swagger = None
if Swagger is not None:
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/",
    }
    swagger = Swagger(
        app,
        config=swagger_config,
        template={
            "swagger": "2.0",
            "info": {
                "title": "RAGFlow API",
                "description": "",
                "version": "1.0.0",
            },
            "securityDefinitions": {
                "ApiKeyAuth": {"type": "apiKey", "name": "Authorization", "in": "header"}
            },
        },
    )

# CORS if available
if CORS is not None:
    CORS(app, supports_credentials=True, max_age=2592000)

app.url_map.strict_slashes = False
app.json_encoder = CustomJSONEncoder  # type: ignore
app.errorhandler(Exception)(server_error_response)
# Provide JSON response for HTTPExceptions explicitly
@app.errorhandler(HTTPException)
def _http_error_handler(e: HTTPException):
    payload = {
        "ok": False,
        "error": e.name,
        "code": e.code,
        "description": e.description,
    }
    return jsonify(payload), e.code

# Sessions (optional)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH", 128 * 1024 * 1024)
)
Session(app)

# commands.register_commands(app)  # optional


def search_pages_path(pages_dir: Path):
    app_path_list = [
        path for path in pages_dir.glob("*_app.py") if not path.name.startswith(".")
    ]
    api_path_list = [
        path for path in pages_dir.glob("*sdk/*.py") if not path.name.startswith(".")
    ]
    app_path_list.extend(api_path_list)
    return app_path_list


def register_page(page_path: Path):
    path = f"{page_path}"

    page_name = page_path.stem
    if page_name.endswith("_app"):
        page_name = page_name[:-4]
    module_name = ".".join(
        page_path.parts[page_path.parts.index("api") : -1] + (page_name,)
    )
    logging.info(module_name)
    spec = spec_from_file_location(module_name, page_path)
    page = module_from_spec(spec)
    page.app = app
    page.manager = Blueprint(page_name, module_name)
    sys.modules[module_name] = page
    spec.loader.exec_module(page)
    page_name = getattr(page, "page_name", page_name)
    sdk_path = "\\sdk\\" if sys.platform.startswith("win") else "/sdk/"
    url_prefix = (
        f"/api/{API_VERSION}" if sdk_path in path else f"/{API_VERSION}/{page_name}"
    )

    app.register_blueprint(page.manager, url_prefix=url_prefix)
    return url_prefix


pages_dir = [
    Path(__file__).parent,
    Path(__file__).parent.parent / "api" / "apps",
    Path(__file__).parent.parent / "api" / "apps" / "sdk",
]

client_urls_prefix = [
    register_page(path) for dir in pages_dir for path in search_pages_path(dir)
]
# Basic health checks
@app.route("/healthz", methods=["GET"])  # liveness
def _healthz():
    return jsonify({"ok": True, "version": API_VERSION})
@app.route(f"/{API_VERSION}/healthz", methods=["GET"])  # versioned health
def _healthz_versioned():
    return jsonify({"ok": True, "version": API_VERSION})
# Simple request logging with latency
@app.before_request
def _start_timer():
    g._t0 = time.time()
@app.after_request
def _log_request(resp):
    try:
        dt = (time.time() - getattr(g, "_t0", time.time())) * 1000.0
        app.logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.path,
            resp.status_code,
            dt,
        )
    except Exception:  # pragma: no cover
        pass
    return resp


@app.teardown_request
def _db_close(exc):
    pass
