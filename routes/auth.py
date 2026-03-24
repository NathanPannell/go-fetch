from flask import Blueprint, request, jsonify
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
import pymongo
from clients import users_collection
from config import PEPPER

auth_bp = Blueprint('auth', __name__)


def hash_password(password):
    return generate_password_hash(password + PEPPER).decode('utf-8')


@auth_bp.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True)
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Invalid request"}), 400

    if users_collection.find_one({"username": data['username']}):
        return jsonify({"error": "Username already exists"}), 409

    hashed_password = hash_password(data['password'])
    new_user = {
        "username": data['username'],
        "hashed_password": hashed_password
    }

    try:
        result = users_collection.insert_one(new_user)
        user_id = str(result.inserted_id)
    except pymongo.errors.DuplicateKeyError:
        return jsonify({"error": "Username already exists"}), 409

    return jsonify({
        "message": "User created successfully",
        "user_id": user_id
    }), 200


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Invalid request"}), 400

    user = users_collection.find_one({"username": data['username']})
    if user and check_password_hash(user['hashed_password'], data['password'] + PEPPER):
        access_token = create_access_token(identity=user['username'])
        return jsonify({
            "token": access_token,
            "user_id": str(user['_id'])
        }), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401


# For debugging only
@auth_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    current_user = get_jwt_identity()
    return jsonify({
        "all_users": [
            {
                "username": u["username"],
                "hashed_password": u["hashed_password"],
                "user_id": str(u["_id"])
            } for u in users_collection.find()
        ],
        "current_user": current_user
    }), 200
