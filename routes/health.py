from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    if not current_app.config.get("DB_READY"):
        return jsonify({"status": "starting"}), 401
    return jsonify({"status": "ok"}), 200
