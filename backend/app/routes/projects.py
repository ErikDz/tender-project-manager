"""Project management routes."""

from flask import Blueprint, request, jsonify, g, current_app
from ..middleware.auth import require_auth

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("", methods=["GET"])
@require_auth
def list_projects():
    """List all projects for the user's organization."""
    supabase = current_app.supabase
    result = supabase.table("projects") \
        .select("*, documents(count)") \
        .eq("organization_id", g.organization_id) \
        .order("created_at", desc=True) \
        .execute()
    return jsonify(result.data)


@projects_bp.route("", methods=["POST"])
@require_auth
def create_project():
    """Create a new project."""
    data = request.get_json()
    supabase = current_app.supabase

    project = supabase.table("projects").insert({
        "organization_id": g.organization_id,
        "name": data["name"],
        "description": data.get("description", ""),
        "tender_number": data.get("tender_number", ""),
        "deadline": data.get("deadline"),
    }).execute()

    return jsonify(project.data[0]), 201


@projects_bp.route("/<project_id>", methods=["GET"])
@require_auth
def get_project(project_id):
    """Get project details with stats."""
    supabase = current_app.supabase

    project = supabase.table("projects") \
        .select("*") \
        .eq("id", project_id) \
        .eq("organization_id", g.organization_id) \
        .single() \
        .execute()

    if not project.data:
        return jsonify({"error": "Project not found"}), 404

    # Get node stats
    nodes = supabase.table("nodes") \
        .select("type, status") \
        .eq("project_id", project_id) \
        .execute()

    total = len(nodes.data)
    completed = sum(1 for n in nodes.data if n["status"] == "completed")
    by_type = {}
    for n in nodes.data:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1

    result = project.data
    result["stats"] = {
        "total_nodes": total,
        "completed": completed,
        "completion_pct": round(completed / total * 100, 1) if total > 0 else 0,
        "by_type": by_type,
    }
    return jsonify(result)


@projects_bp.route("/<project_id>", methods=["PUT"])
@require_auth
def update_project(project_id):
    """Update project details."""
    data = request.get_json()
    supabase = current_app.supabase

    result = supabase.table("projects") \
        .update(data) \
        .eq("id", project_id) \
        .eq("organization_id", g.organization_id) \
        .execute()

    if not result.data:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(result.data[0])


@projects_bp.route("/<project_id>", methods=["DELETE"])
@require_auth
def delete_project(project_id):
    """Delete a project and all its data."""
    supabase = current_app.supabase

    supabase.table("projects") \
        .delete() \
        .eq("id", project_id) \
        .eq("organization_id", g.organization_id) \
        .execute()

    return jsonify({"status": "deleted"}), 200
