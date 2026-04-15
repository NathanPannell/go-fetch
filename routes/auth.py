from flask import Blueprint, request, jsonify
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from pymongo.errors import DuplicateKeyError
from clients import users_collection
from config import PEPPER

auth_bp = Blueprint("auth", __name__)


def hash_password(password):
    return generate_password_hash(password + PEPPER).decode("utf-8")


@auth_bp.route("/auth/signup", methods=["POST"])
def signup():
    creds = request.get_json(silent=True)
    if not creds or "username" not in creds or "password" not in creds:
        return jsonify({"error": "Invalid request"}), 400

    new_user = {
        "username": creds["username"],
        "hashed_password": hash_password(creds["password"]),
    }
    try:
        result = users_collection.insert_one(new_user)
    except DuplicateKeyError:
        return jsonify({"error": "Username already exists"}), 409

    return jsonify({"message": "User created successfully", "user_id": str(result.inserted_id)}), 200


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    creds = request.get_json(silent=True)
    if not creds or "username" not in creds or "password" not in creds:
        return jsonify({"error": "Invalid request"}), 400

    user = users_collection.find_one({"username": creds["username"]})
    if user and check_password_hash(
        user["hashed_password"], creds["password"] + PEPPER
    ):
        access_token = create_access_token(identity=str(user["_id"]))
        return jsonify({"token": access_token, "user_id": str(user["_id"])}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401
