"""Document processing routes — triggers AI extraction pipeline."""

import threading
from flask import Blueprint, request, jsonify, g, current_app, Response
from ..middleware.auth import require_auth
from ..services.extraction_service import ExtractionService

processing_bp = Blueprint("processing", __name__)


@processing_bp.route("/projects/<project_id>/process", methods=["POST"])
@require_auth
def start_processing(project_id):
    """Start AI extraction for a project. Returns job_id for progress tracking."""
    supabase = current_app.supabase
    force_full = request.args.get("full", "false").lower() == "true"

    # Verify project belongs to org
    project = supabase.table("projects") \
        .select("id") \
        .eq("id", project_id) \
        .eq("organization_id", g.organization_id) \
        .single() \
        .execute()

    if not project.data:
        return jsonify({"error": "Project not found"}), 404

    # Create processing job
    job = supabase.table("processing_jobs").insert({
        "project_id": project_id,
        "job_type": "extract",
        "status": "pending",
    }).execute()

    job_id = job.data[0]["id"]

    # Run extraction in background thread
    service = ExtractionService(supabase)
    thread = threading.Thread(
        target=service.run_extraction,
        args=(project_id, job_id, force_full),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"}), 202


@processing_bp.route("/projects/<project_id>/process/active", methods=["GET"])
@require_auth
def get_active_job(project_id):
    """Get the most recent running/pending job for a project, if any."""
    supabase = current_app.supabase

    job = supabase.table("processing_jobs") \
        .select("*") \
        .eq("project_id", project_id) \
        .in_("status", ["pending", "running"]) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if not job.data:
        return jsonify({"active": False})
    return jsonify({"active": True, "job": job.data[0]})


@processing_bp.route("/jobs/<job_id>", methods=["GET"])
@require_auth
def get_job_status(job_id):
    """Get processing job status and progress."""
    supabase = current_app.supabase

    job = supabase.table("processing_jobs") \
        .select("*") \
        .eq("id", job_id) \
        .single() \
        .execute()

    if not job.data:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.data)


@processing_bp.route("/jobs/<job_id>/stream", methods=["GET"])
@require_auth
def stream_job_progress(job_id):
    """SSE stream for real-time job progress updates."""
    import time
    import json

    supabase = current_app.supabase

    def generate():
        while True:
            job = supabase.table("processing_jobs") \
                .select("*") \
                .eq("id", job_id) \
                .single() \
                .execute()

            if not job.data:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            yield f"data: {json.dumps(job.data)}\n\n"

            if job.data["status"] in ("completed", "failed"):
                break

            time.sleep(1)

    return Response(generate(), mimetype="text/event-stream")
