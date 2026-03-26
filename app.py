from flask import Flask
from flask_jwt_extended import JWTManager
from config import JWT_SECRET_KEY
from clients import init_vector_search_index
from routes.health import health_bp
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.search import search_bp

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY
JWTManager(app)

app.register_blueprint(health_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(search_bp)

init_vector_search_index()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
