"""Graph service — adapter between core.graph.RequirementGraph and Supabase."""

from datetime import datetime
from core.graph import RequirementGraph, Node, NodeType, EdgeType, CompletionStatus, Edge


class GraphService:
    """Loads/saves RequirementGraph from/to Supabase database."""

    def __init__(self, supabase_client):
        self.db = supabase_client

    def load_graph(self, project_id: str) -> RequirementGraph:
        """Load a RequirementGraph from Supabase database records."""
        graph = RequirementGraph()

        # Load all nodes for this project with joined document filename
        nodes_result = self.db.table("nodes") \
            .select("*, documents(filename)") \
            .eq("project_id", project_id) \
            .execute()

        for row in nodes_result.data:
            # Extract joined document filename
            source_doc = None
            doc_data = row.get("documents")
            if doc_data and isinstance(doc_data, dict):
                source_doc = doc_data.get("filename")

            node = Node(
                id=row["id"],
                type=NodeType(row["type"]),
                title=row["title"],
                description=row.get("description") or "",
                status=CompletionStatus(row.get("status", "not_started")),
                source_document=source_doc,
                source_text=row.get("source_text") or "",
                source_location=row.get("source_location") or "",
                checkbox_state=row.get("is_checked"),
                confidence=row.get("confidence", 1.0),
                tags=row.get("tags") or [],
                metadata=row.get("metadata") or {},
            )

            # Parse deadline if present
            if row.get("deadline"):
                try:
                    node.deadline = datetime.fromisoformat(row["deadline"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            graph.add_node(node)

        # Load all edges for this project
        edges_result = self.db.table("edges") \
            .select("*") \
            .eq("project_id", project_id) \
            .execute()

        for row in edges_result.data:
            edge = Edge(
                id=row["id"],
                source_id=row["source_node_id"],
                target_id=row["target_node_id"],
                type=EdgeType(row["type"]),
                description=row.get("description") or "",
                confidence=row.get("confidence", 1.0),
                metadata=row.get("metadata") or {},
            )
            graph.add_edge(edge)

        return graph

    def save_graph(self, project_id: str, graph: RequirementGraph, document_id_map: dict = None):
        """Save a RequirementGraph to Supabase database.

        Args:
            project_id: The project UUID
            graph: The in-memory RequirementGraph
            document_id_map: Optional mapping of source_document filenames to document UUIDs
        """
        document_id_map = document_id_map or {}

        # Batch upsert nodes
        node_rows = []
        for node in graph.nodes.values():
            node_data = {
                "id": node.id,
                "project_id": project_id,
                "type": node.type.value,
                "title": node.title,
                "description": node.description,
                "status": node.status.value,
                "source_text": node.source_text or "",
                "source_location": node.source_location or "",
                "is_checked": node.checkbox_state,
                "confidence": node.confidence,
                "tags": node.tags,
                "metadata": node.metadata,
            }

            if node.deadline:
                node_data["deadline"] = node.deadline.isoformat()

            # Map source document filename to document ID
            if node.source_document and node.source_document in document_id_map:
                node_data["document_id"] = document_id_map[node.source_document]

            node_rows.append(node_data)

        # Upsert in batches of 50
        for i in range(0, len(node_rows), 50):
            batch = node_rows[i:i + 50]
            self.db.table("nodes").upsert(batch).execute()

        # Batch upsert edges
        edge_rows = []
        for edge in graph.edges.values():
            edge_rows.append({
                "id": edge.id,
                "project_id": project_id,
                "source_node_id": edge.source_id,
                "target_node_id": edge.target_id,
                "type": edge.type.value,
                "description": edge.description,
                "confidence": edge.confidence,
                "metadata": edge.metadata,
            })

        for i in range(0, len(edge_rows), 50):
            batch = edge_rows[i:i + 50]
            self.db.table("edges").upsert(batch).execute()

    def update_node_status(self, node_id: str, status: str):
        """Update a single node's status."""
        self.db.table("nodes") \
            .update({"status": status}) \
            .eq("id", node_id) \
            .execute()
