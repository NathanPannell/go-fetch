import os
from datetime import datetime, timezone
from uuid import uuid4
from flask import Blueprint, request, jsonify
from tasks import process_document
from flask_jwt_extended import jwt_required, get_jwt_identity
from clients import (
    users_collection,
    documents_collection,
    document_chunks_collection,
    minio_client,
    minio_pdf_bucket_name,
)
from bson import ObjectId

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/documents", methods=["POST"])
@jwt_required()
def upload_file():
    file = request.files.get("file")
    if not file or file.filename == "" or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Unable to find PDF"}), 400

    owner_id = get_jwt_identity()
    filename = file.filename
    upload_date = datetime.now(timezone.utc).isoformat() + "Z"

    new_doc = {
        "owner_id": owner_id,
        "filename": filename,
        "upload_date": upload_date,
        "status": "processing",
        "page_count": None,
    }
    result = documents_collection.insert_one(new_doc)
    document_id = str(result.inserted_id)

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    minio_client.put_object(
        minio_pdf_bucket_name, document_id, file, size, content_type="application/pdf"
    )

    process_document.delay(document_id, owner_id, filename)

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
    owner_id = get_jwt_identity()
    docs = list(documents_collection.find({"owner_id": owner_id}))
    result = [
        {
            "document_id": str(d["_id"]),
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
    owner_id = get_jwt_identity()

    doc = documents_collection.find_one(
        {"_id": ObjectId(document_id), "owner_id": owner_id}
    )
    if not doc:
        return jsonify({"error": "Document not found or not owned by user"}), 404

    documents_collection.delete_one({"_id": ObjectId(document_id), "owner_id": owner_id})
    document_chunks_collection.delete_many(
        {"document_id": document_id, "owner_id": owner_id}
    )
    minio_client.remove_object(minio_pdf_bucket_name, document_id)

    return (
        jsonify(
            {
                "message": "Document and all associated data deleted",
                "document_id": document_id,
            }
        ),
        200,
    )
