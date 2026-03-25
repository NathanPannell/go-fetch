import os
from datetime import datetime
from uuid import uuid4
from flask import Blueprint, request, jsonify
from tasks import process_document
from flask_jwt_extended import jwt_required, get_jwt_identity
from clients import (
    users_collection,
    documents_collection,
    document_chunks_collection,
    minio_client,
    bucket_name,
)

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/documents", methods=["POST"])
@jwt_required()
def upload_file():
    file = request.files.get("file")
    if not file or file.filename == "" or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Unable to find PDF"}), 400

    user_id = get_jwt_identity()
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "Invalid JWT"}), 401

    document_id = str(uuid4())
    filename = file.filename
    upload_date = datetime.now(datetime.timezone.utc).isoformat() + "Z"

    new_doc = {
        "owner_id": user_id,
        "document_id": document_id,
        "filename": filename,
        "upload_date": upload_date,
        "status": "processing",
        "page_count": None,
    }
    documents_collection.insert_one(new_doc)

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    minio_client.put_object(
        bucket_name, document_id, file, size, content_type="application/pdf"
    )

    process_document.delay(document_id, user_id, filename)

    return (
        jsonify(
            {
                "message": "PDF uploaded, processing started",
                "document_id": document_id,
                "status": "processing",
            }
        ),
        202,
    )


@documents_bp.route("/documents", methods=["GET"])
@jwt_required()
def list_documents():
    user_id = get_jwt_identity()
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "Invalid JWT"}), 401

    docs = list(documents_collection.find({"owner_id": user_id}))
    result = [
        {
            "document_id": d["document_id"],
            "filename": d["filename"],
            "upload_date": d["upload_date"],
            "status": d["status"],
            "page_count": d.get("page_count"),
        }
        for d in docs
    ]
    return jsonify(result), 200


@documents_bp.route("/documents/<document_id>", methods=["DELETE"])
@jwt_required()
def delete_document(document_id):
    user_id = get_jwt_identity()
    user = users_collection.find_one({"_id": user_id})
    if not user:
        return jsonify({"error": "Invalid JWT"}), 401

    doc = documents_collection.find_one(
        {"document_id": document_id, "owner_id": user_id}
    )
    if not doc:
        return jsonify({"error": "Document not found or not owned by user"}), 404

    documents_collection.delete_one({"document_id": document_id, "owner_id": user_id})
    document_chunks_collection.delete_many(
        {"document_id": document_id, "owner_id": user_id}
    )
    minio_client.remove_object(bucket_name, document_id)

    return (
        jsonify(
            {
                "message": "Document and all associated data deleted",
                "document_id": document_id,
            }
        ),
        200,
    )
