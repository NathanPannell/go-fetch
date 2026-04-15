import os
import signal
import sys
import time

import pymongo.errors
from flask import Flask
from flask_jwt_extended import JWTManager
from werkzeug.middleware.profiler import ProfilerMiddleware
from config import JWT_SECRET_KEY
from clients import init_vector_search_index, init_db_indexes
from routes.health import health_bp
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.search import search_bp

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
app.config["DB_READY"] = False
JWTManager(app)

app.register_blueprint(health_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(search_bp)

for _attempt in range(12):
    try:
        init_db_indexes()
        init_vector_search_index()
        app.config["DB_READY"] = True
        break
    except pymongo.errors.PyMongoError:
        if _attempt < 11:
            time.sleep(5)
        else:
            raise

if os.environ.get("PROFILING_ENABLED", "").lower() == "true":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    _traces_dir = "/profile/results/traces"
    os.makedirs(_traces_dir, exist_ok=True)
    app.wsgi_app = ProfilerMiddleware(
        app.wsgi_app,
        restrictions=[30],
        profile_dir=_traces_dir,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
