import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from uuid import uuid4

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

db = SQLAlchemy(app)
jwt = JWTManager(app)

PEPPER = os.getenv('PEPPER')

class User(db.Model):
    username = db.Column(db.String(80), primary_key=True)
    hashed_password = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.String(80), nullable=False) # Required for spec, not used.

    def to_dict(self):
        return {
            "username": self.username,
            "hashed_password": self.hashed_password,
            "user_id": self.user_id
        }

with app.app_context():
    db.create_all()
    print("Database created")

# Use bcrypt to hash password with salt.
# Pepper is added via an enviroment variable.
def hash_password(password):
    return generate_password_hash(password + PEPPER).decode('utf-8')

@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True)
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Invalid request"}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 409

    hashed_password = hash_password(data['password'])
    new_user = User(
        username=data['username'], 
        hashed_password=hashed_password, 
        user_id=str(uuid4())
    )

    db.session.add(new_user)
    db.session.commit()
    return jsonify({
        "message": "User created successfully", 
        "user_id": new_user.user_id
    }), 201

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Invalid request"}), 400

    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.hashed_password, data['password'] + PEPPER):
        access_token = create_access_token(identity=user.username)
        return jsonify({
            "token": access_token,
            "user_id": user.user_id
        }), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401

# For debugging only
@app.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    current_user = get_jwt_identity()
    return jsonify({
        "all_users": [i.to_dict() for i in User.query.all()],
        "current_user": current_user
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
