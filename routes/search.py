import hashlib
import json

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from clients import users_collection, document_chunks_collection, embedding_model, redis_client
from config import EMBEDDING_CACHE_TTL, SEARCH_CACHE_TTL

search_bp = Blueprint("search", __name__)


def _query_hash(query_text):
    return hashlib.sha256(query_text.encode()).hexdigest()


@search_bp.route("/search", methods=["GET"])
@jwt_required()
def search():
    query_text = request.args.get("q", "").strip()
    if not query_text:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    owner_id = get_jwt_identity()
    qhash = _query_hash(query_text)

    result_key = f"search:{owner_id}:{qhash}"
    embedding_key = f"embedding:{qhash}"

    # Layer 1: per-user result cache
    try:
        cached_results = redis_client.get(result_key)
        if cached_results is not None:
            response = jsonify(json.loads(cached_results))
            response.headers["X-Cache"] = "HIT"
            return response, 200
    except Exception:
        pass

    # Layer 2: global embedding cache
    try:
        cached_embedding = redis_client.get(embedding_key)
    except Exception:
        cached_embedding = None

    if cached_embedding is not None:
        query_vector = json.loads(cached_embedding)
    else:
        query_vector = embedding_model.encode(query_text).tolist()
        try:
            redis_client.set(embedding_key, json.dumps(query_vector), ex=EMBEDDING_CACHE_TTL)
        except Exception:
            pass

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "vector_embedding",
                "queryVector": query_vector,
                "numCandidates": 100,
                "limit": 5,
                "filter": {"owner_id": owner_id},
            }
        },
        {
            "$project": {
                "_id": 0,
                "text": 1,
                "filename": 1,
                "document_id": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = list(document_chunks_collection.aggregate(pipeline))
    try:
        redis_client.set(result_key, json.dumps(results), ex=SEARCH_CACHE_TTL)
    except Exception:
        pass

    response = jsonify(results)
    response.headers["X-Cache"] = "MISS"
    return response, 200
