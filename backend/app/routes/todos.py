"""To-do list routes."""

from flask import Blueprint, request, jsonify, g, current_app
from ..middleware.auth import require_auth
from ..services.graph_service import GraphService

todos_bp = Blueprint("todos", __name__)


def _serialize_category(cat):
    """Serialize a TodoCategory for JSON response."""
    return {
        "name": cat.name,
        "description": cat.description,
        "total": cat.total_count,
        "completed": cat.completed_count,
        "completion_percentage": cat.completion_percentage,
        "items": [item.to_dict() for item in cat.items],
    }


@todos_bp.route("/<project_id>/todos", methods=["GET"])
@require_auth
def get_todos(project_id):
    """Get full categorized to-do list."""
    from core.todo import TodoGenerator

    service = GraphService(current_app.supabase)
    graph = service.load_graph(project_id)

    generator = TodoGenerator(graph)
    todo_list = generator.generate()

    return jsonify({
        "categories": [_serialize_category(cat) for cat in todo_list],
        "summary": generator.get_summary(),
    })


@todos_bp.route("/<project_id>/todos/critical", methods=["GET"])
@require_auth
def get_critical_todos(project_id):
    """Get critical items only."""
    from core.todo import TodoGenerator

    service = GraphService(current_app.supabase)
    graph = service.load_graph(project_id)

    generator = TodoGenerator(graph)
    critical = generator.get_critical_items()

    return jsonify({"critical_items": [item.to_dict() for item in critical]})


@todos_bp.route("/<project_id>/todos/<node_id>/complete", methods=["PUT"])
@require_auth
def mark_complete(project_id, node_id):
    """Mark a to-do item as complete."""
    supabase = current_app.supabase

    result = supabase.table("nodes") \
        .update({"status": "completed"}) \
        .eq("id", node_id) \
        .eq("project_id", project_id) \
        .execute()

    if not result.data:
        return jsonify({"error": "Node not found"}), 404
    return jsonify(result.data[0])


@todos_bp.route("/<project_id>/todos/<node_id>/status", methods=["PUT"])
@require_auth
def update_status(project_id, node_id):
    """Set any status on a to-do item."""
    data = request.get_json()
    status = data.get("status")

    valid_statuses = {"not_started", "in_progress", "completed", "not_applicable", "blocked"}
    if status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

    supabase = current_app.supabase
    result = supabase.table("nodes") \
        .update({"status": status}) \
        .eq("id", node_id) \
        .eq("project_id", project_id) \
        .execute()

    if not result.data:
        return jsonify({"error": "Node not found"}), 404
    return jsonify(result.data[0])


@todos_bp.route("/<project_id>/todos/export", methods=["GET"])
@require_auth
def export_todos(project_id):
    """Export to-do list as markdown."""
    from core.todo import TodoGenerator

    service = GraphService(current_app.supabase)
    graph = service.load_graph(project_id)

    generator = TodoGenerator(graph)
    markdown = generator.to_markdown()

    return jsonify({"markdown": markdown})
