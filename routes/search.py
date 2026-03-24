from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from clients import users_collection, document_chunks_collection, embedding_model

search_bp = Blueprint('search', __name__)


@search_bp.route('/search', methods=['GET'])
@jwt_required()
def search():
    query_text = request.args.get('q', '').strip()
    if not query_text:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    username = get_jwt_identity()
    user = users_collection.find_one({"username": username})
    if not user:
        return jsonify({"error": "User not found"}), 404

    owner_id = str(user['_id'])
    query_vector = embedding_model.encode(query_text).tolist()

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "vector_embedding",
                "queryVector": query_vector,
                "numCandidates": 100,
                "limit": 50
            }
        },
        {
            "$match": {"owner_id": owner_id}
        },
        {
            "$limit": 5
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
    return jsonify(results), 200
