"""Document management routes."""

import os
import uuid
from flask import Blueprint, request, jsonify, g, current_app
from ..middleware.auth import require_auth

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/<project_id>/documents", methods=["GET"])
@require_auth
def list_documents(project_id):
    """List all documents in a project."""
    supabase = current_app.supabase
    result = supabase.table("documents") \
        .select("*") \
        .eq("project_id", project_id) \
        .order("filename") \
        .execute()
    return jsonify(result.data)


@documents_bp.route("/<project_id>/documents/upload", methods=["POST"])
@require_auth
def upload_documents(project_id):
    """Upload one or more documents to a project."""
    supabase = current_app.supabase

    # Verify project belongs to org
    project = supabase.table("projects") \
        .select("id") \
        .eq("id", project_id) \
        .eq("organization_id", g.organization_id) \
        .single() \
        .execute()

    if not project.data:
        return jsonify({"error": "Project not found"}), 404

    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    uploaded = []

    for file in files:
        if not file.filename:
            continue

        # Generate storage path
        file_ext = os.path.splitext(file.filename)[1]
        storage_path = f"{project_id}/{uuid.uuid4()}{file_ext}"

        # Upload to Supabase Storage
        file_bytes = file.read()
        supabase.storage.from_("documents").upload(
            storage_path,
            file_bytes,
            {"content-type": file.content_type or "application/octet-stream"},
        )

        # Create document record
        doc = supabase.table("documents").insert({
            "project_id": project_id,
            "filename": file.filename,
            "storage_path": storage_path,
            "file_type": file_ext.lstrip(".").lower(),
            "file_size": len(file_bytes),
        }).execute()

        uploaded.append(doc.data[0])

    return jsonify({"uploaded": uploaded, "count": len(uploaded)}), 201


@documents_bp.route("/<project_id>/documents/<doc_id>", methods=["DELETE"])
@require_auth
def delete_document(project_id, doc_id):
    """Delete a document."""
    supabase = current_app.supabase

    # Get storage path before deleting
    doc = supabase.table("documents") \
        .select("storage_path") \
        .eq("id", doc_id) \
        .eq("project_id", project_id) \
        .single() \
        .execute()

    if doc.data:
        # Remove from storage
        supabase.storage.from_("documents").remove([doc.data["storage_path"]])
        # Remove from DB
        supabase.table("documents").delete().eq("id", doc_id).execute()

    return jsonify({"status": "deleted"}), 200
