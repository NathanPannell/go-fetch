import os
from datetime import datetime
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
import pymongo
from minio import Minio
from dotenv import load_dotenv
from flask_bcrypt import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from uuid import uuid4
from sentence_transformers import SentenceTransformer

load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

mongo_client = MongoClient(os.getenv('MONGO_URI'))
db = mongo_client.get_database() if mongo_client.get_database().name else mongo_client['flaskdb']
jwt = JWTManager(app)

PEPPER = os.getenv('PEPPER')

users_collection = db['Users']
documents_collection = db['Documents']
document_chunks_collection = db['DocumentChunks']

users_collection.create_index([("username", pymongo.ASCENDING)], unique=True)
print("Database connected, collections initialized")

def init_vector_search_index():
    existing = list(document_chunks_collection.list_search_indexes())
    if any(idx.get("name") == "vector_index" for idx in existing):
        print("Vector search index already exists")
        return
    model_def = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "vector_embedding",
                    "numDimensions": 384,
                    "similarity": "cosine"
                }
            ]
        },
        name="vector_index",
        type="vectorSearch",
    )
    document_chunks_collection.create_search_index(model=model_def)
    print("Vector search index created")

init_vector_search_index()

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize MinIO
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)
bucket_name = "raw-pdfs"
if not minio_client.bucket_exists(bucket_name):
    minio_client.make_bucket(bucket_name)
    print(f"MinIO bucket '{bucket_name}' created")
# Use bcrypt to hash password with salt.
# Pepper is added via an enviroment variable.
def hash_password(password):
    return generate_password_hash(password + PEPPER).decode('utf-8')

@app.route('/auth/signup', methods=['POST'])
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
    }), 201

@app.route('/auth/login', methods=['POST'])
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
@app.route('/users', methods=['GET'])
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

@app.route('/api/upload', methods=['POST'])
@jwt_required()
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDFs are allowed"}), 400

    username = get_jwt_identity()
    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    owner_id = str(user['_id'])
    document_id = str(uuid4())
    filename = file.filename
    upload_date = datetime.utcnow().isoformat() + "Z"
    
    new_doc = {
        "owner_id": owner_id,
        "document_id": document_id,
        "filename": filename,
        "upload_date": upload_date,
        "status": "pending",
        "page_count": 0
    }
    documents_collection.insert_one(new_doc)
    
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    minio_client.put_object(bucket_name, document_id, file, size, content_type="application/pdf")
    
    from tasks import process_document
    process_document.delay(document_id, owner_id, filename)
    
    return jsonify({"document_id": document_id}), 202

@app.route('/api/user-data/<username>', methods=['GET'])
@jwt_required()
def get_user_data(username):
    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    owner_id = str(user['_id'])
    
    # Fetch documents
    documents = list(documents_collection.find({"owner_id": owner_id}))
    for doc in documents:
        doc['_id'] = str(doc['_id'])
        
    # Fetch chunks
    chunks = list(document_chunks_collection.find({"owner_id": owner_id}))
    for chunk in chunks:
        chunk['_id'] = str(chunk['_id'])
        
    return jsonify({
        "username": username,
        "user_id": owner_id,
        "documents": documents,
        "document_chunks": chunks
    }), 200

@app.route('/api/search', methods=['POST'])
@jwt_required()
def search():
    data = request.get_json(silent=True)
    if not data or 'query' not in data:
        return jsonify({"error": "Missing 'query' field"}), 400

    query_text = data['query']
    limit = int(data.get('limit', 5))

    query_vector = embedding_model.encode(query_text).tolist()

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "vector_embedding",
                "queryVector": query_vector,
                "numCandidates": limit * 10,
                "limit": limit
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "filename": 1,
                "document_id": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    results = list(document_chunks_collection.aggregate(pipeline))
    return jsonify({"results": results}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
