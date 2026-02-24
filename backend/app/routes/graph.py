"""Graph visualization and node management routes."""

from flask import Blueprint, request, jsonify, g, current_app
from ..middleware.auth import require_auth
from ..services.graph_service import GraphService

graph_bp = Blueprint("graph", __name__)


@graph_bp.route("/<project_id>/graph", methods=["GET"])
@require_auth
def get_graph(project_id):
    """Get full graph (nodes + edges) for a project."""
    supabase = current_app.supabase

    nodes = supabase.table("nodes") \
        .select("*, documents(filename)") \
        .eq("project_id", project_id) \
        .execute()

    edges = supabase.table("edges") \
        .select("*") \
        .eq("project_id", project_id) \
        .execute()

    return jsonify({
        "nodes": nodes.data,
        "edges": edges.data,
        "total_nodes": len(nodes.data),
        "total_edges": len(edges.data),
    })


@graph_bp.route("/<project_id>/graph/stats", methods=["GET"])
@require_auth
def get_graph_stats(project_id):
    """Get completion statistics for a project."""
    service = GraphService(current_app.supabase)
    graph = service.load_graph(project_id)
    stats = graph.get_completion_stats()
    return jsonify(stats)


@graph_bp.route("/<project_id>/nodes/<node_id>", methods=["PUT"])
@require_auth
def update_node(project_id, node_id):
    """Update a node's status, notes, etc."""
    data = request.get_json()
    supabase = current_app.supabase

    # Only allow updating specific fields (updated_at handled by DB trigger)
    allowed = {"status", "notes", "is_checked"}
    update_data = {k: v for k, v in data.items() if k in allowed}

    result = supabase.table("nodes") \
        .update(update_data) \
        .eq("id", node_id) \
        .eq("project_id", project_id) \
        .execute()

    if not result.data:
        return jsonify({"error": "Node not found"}), 404
    return jsonify(result.data[0])
