"""
Tender Requirement Graph

A connected graph that evolves as documents are read and requirements discovered.
Nodes represent requirements, documents, conditions, and actions.
Edges represent relationships: depends_on, required_by, conditional_on, etc.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid
import json


class NodeType(Enum):
    DOCUMENT = "document"           # A physical document that must be submitted
    REQUIREMENT = "requirement"     # Something that must be done/provided
    CONDITION = "condition"         # A conditional clause (if X then Y)
    CHECKBOX = "checkbox"           # A specific checkbox to be checked
    SIGNATURE = "signature"         # A signature requirement
    FIELD = "field"                 # A form field to fill
    ATTACHMENT = "attachment"       # An attachment to include
    DEADLINE = "deadline"           # A time-based requirement


class EdgeType(Enum):
    REQUIRES = "requires"           # A requires B (A needs B to be complete)
    REQUIRED_BY = "required_by"     # A is required by B
    CONDITIONAL_ON = "conditional_on"  # A only applies if condition B is met
    TRIGGERS = "triggers"           # If A is checked/done, it triggers B
    PART_OF = "part_of"            # A is part of document B
    REFERENCES = "references"       # A references B
    MUTUALLY_EXCLUSIVE = "mutually_exclusive"  # A and B cannot both be selected
    DEPENDS_ON = "depends_on"       # A depends on B being completed first


class CompletionStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_APPLICABLE = "not_applicable"  # Due to unmet condition
    BLOCKED = "blocked"             # Waiting on dependency


@dataclass
class Node:
    """A node in the requirement graph."""
    id: str
    type: NodeType
    title: str
    description: str
    status: CompletionStatus = CompletionStatus.NOT_STARTED

    # Source tracking
    source_document: Optional[str] = None  # Which document this was found in
    source_location: Optional[str] = None  # Page, section, or line reference
    source_text: Optional[str] = None      # Original text that created this node

    # For checkboxes
    checkbox_state: Optional[bool] = None  # True=checked, False=unchecked, None=N/A

    # For conditions
    condition_met: Optional[bool] = None   # Whether condition is satisfied

    # For deadlines
    deadline: Optional[datetime] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0  # AI confidence in this extraction (0-1)
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # Human notes
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "source_document": self.source_document,
            "source_location": self.source_location,
            "source_text": self.source_text,
            "checkbox_state": self.checkbox_state,
            "condition_met": self.condition_met,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "confidence": self.confidence,
            "tags": self.tags,
            "metadata": self.metadata,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Node":
        return cls(
            id=data["id"],
            type=NodeType(data["type"]),
            title=data["title"],
            description=data["description"],
            status=CompletionStatus(data["status"]),
            source_document=data.get("source_document"),
            source_location=data.get("source_location"),
            source_text=data.get("source_text"),
            checkbox_state=data.get("checkbox_state"),
            condition_met=data.get("condition_met"),
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            confidence=data.get("confidence", 1.0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            notes=data.get("notes"),
        )


@dataclass
class Edge:
    """An edge connecting two nodes."""
    id: str
    source_id: str
    target_id: str
    type: EdgeType
    description: Optional[str] = None
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type.value,
            "description": self.description,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Edge":
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            type=EdgeType(data["type"]),
            description=data.get("description"),
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )


class RequirementGraph:
    """
    The evolving graph of tender requirements.

    This graph grows as documents are processed. The AI extracts requirements
    and relationships, adding nodes and edges incrementally. The graph can
    be queried to generate to-do lists, check completion status, and identify
    blockers.
    """

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self._adjacency: dict[str, list[str]] = {}  # node_id -> [edge_ids]
        self._reverse_adjacency: dict[str, list[str]] = {}  # node_id -> [incoming edge_ids]

    def add_node(self, node: Node) -> Node:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = []
        return node

    def create_node(
        self,
        type: NodeType,
        title: str,
        description: str,
        **kwargs
    ) -> Node:
        """Create and add a new node."""
        node = Node(
            id=str(uuid.uuid4()),
            type=type,
            title=title,
            description=description,
            **kwargs
        )
        return self.add_node(node)

    def add_edge(self, edge: Edge) -> Edge:
        """Add an edge to the graph."""
        self.edges[edge.id] = edge

        if edge.source_id not in self._adjacency:
            self._adjacency[edge.source_id] = []
        self._adjacency[edge.source_id].append(edge.id)

        if edge.target_id not in self._reverse_adjacency:
            self._reverse_adjacency[edge.target_id] = []
        self._reverse_adjacency[edge.target_id].append(edge.id)

        return edge

    def connect(
        self,
        source_id: str,
        target_id: str,
        type: EdgeType,
        description: Optional[str] = None,
        **kwargs
    ) -> Edge:
        """Create and add an edge between two nodes."""
        edge = Edge(
            id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            type=type,
            description=description,
            **kwargs
        )
        return self.add_edge(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        """Get all edges originating from a node."""
        edge_ids = self._adjacency.get(node_id, [])
        return [self.edges[eid] for eid in edge_ids]

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        """Get all edges pointing to a node."""
        edge_ids = self._reverse_adjacency.get(node_id, [])
        return [self.edges[eid] for eid in edge_ids]

    def get_dependencies(self, node_id: str) -> list[Node]:
        """Get all nodes that this node depends on."""
        deps = []
        for edge in self.get_outgoing_edges(node_id):
            if edge.type in (EdgeType.DEPENDS_ON, EdgeType.REQUIRES, EdgeType.CONDITIONAL_ON):
                target = self.get_node(edge.target_id)
                if target:
                    deps.append(target)
        return deps

    def get_dependents(self, node_id: str) -> list[Node]:
        """Get all nodes that depend on this node."""
        deps = []
        for edge in self.get_incoming_edges(node_id):
            if edge.type in (EdgeType.DEPENDS_ON, EdgeType.REQUIRES, EdgeType.CONDITIONAL_ON):
                source = self.get_node(edge.source_id)
                if source:
                    deps.append(source)
        return deps

    def get_nodes_by_type(self, node_type: NodeType) -> list[Node]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes.values() if n.type == node_type]

    def get_nodes_by_status(self, status: CompletionStatus) -> list[Node]:
        """Get all nodes with a specific status."""
        return [n for n in self.nodes.values() if n.status == status]

    def get_nodes_by_document(self, document_path: str) -> list[Node]:
        """Get all nodes extracted from a specific document."""
        return [n for n in self.nodes.values() if n.source_document == document_path]

    def find_nodes(self, query: str) -> list[Node]:
        """Find nodes matching a text query (searches title and description)."""
        query_lower = query.lower()
        return [
            n for n in self.nodes.values()
            if query_lower in n.title.lower() or query_lower in n.description.lower()
        ]

    def update_status(self, node_id: str, status: CompletionStatus) -> Optional[Node]:
        """Update the status of a node and propagate changes."""
        node = self.get_node(node_id)
        if not node:
            return None

        node.status = status
        node.updated_at = datetime.now()

        # If completed, check if any blocked nodes can be unblocked
        if status == CompletionStatus.COMPLETED:
            self._propagate_completion(node_id)

        return node

    def _propagate_completion(self, completed_node_id: str):
        """Check dependents to see if they can be unblocked."""
        for dependent in self.get_dependents(completed_node_id):
            if dependent.status == CompletionStatus.BLOCKED:
                # Check if all dependencies are now complete
                all_deps_complete = all(
                    dep.status == CompletionStatus.COMPLETED
                    for dep in self.get_dependencies(dependent.id)
                )
                if all_deps_complete:
                    dependent.status = CompletionStatus.NOT_STARTED
                    dependent.updated_at = datetime.now()

    def evaluate_conditions(self):
        """Re-evaluate all conditional relationships."""
        for node in self.get_nodes_by_type(NodeType.CONDITION):
            # Find nodes that are conditional on this condition
            for edge in self.get_incoming_edges(node.id):
                if edge.type == EdgeType.CONDITIONAL_ON:
                    dependent = self.get_node(edge.source_id)
                    if dependent:
                        if node.condition_met is False:
                            dependent.status = CompletionStatus.NOT_APPLICABLE
                        elif dependent.status == CompletionStatus.NOT_APPLICABLE:
                            dependent.status = CompletionStatus.NOT_STARTED

    def get_actionable_items(self) -> list[Node]:
        """
        Get all nodes that can be worked on now.
        These are nodes that are NOT_STARTED and have no incomplete dependencies.
        """
        actionable = []
        for node in self.nodes.values():
            if node.status not in (CompletionStatus.NOT_STARTED, CompletionStatus.IN_PROGRESS):
                continue

            # Check if all dependencies are complete
            deps = self.get_dependencies(node.id)
            all_deps_complete = all(
                dep.status in (CompletionStatus.COMPLETED, CompletionStatus.NOT_APPLICABLE)
                for dep in deps
            )

            if all_deps_complete:
                actionable.append(node)

        return actionable

    def get_completion_stats(self) -> dict:
        """Get statistics about completion status."""
        stats = {status.value: 0 for status in CompletionStatus}
        for node in self.nodes.values():
            stats[node.status.value] += 1

        total = len(self.nodes)
        completed = stats[CompletionStatus.COMPLETED.value]
        not_applicable = stats[CompletionStatus.NOT_APPLICABLE.value]

        applicable_total = total - not_applicable
        percentage = (completed / applicable_total * 100) if applicable_total > 0 else 0

        return {
            "total_nodes": total,
            "by_status": stats,
            "completion_percentage": round(percentage, 1),
            "applicable_items": applicable_total,
            "completed_items": completed,
        }

    def get_critical_path(self) -> list[Node]:
        """
        Find nodes that are blocking the most other nodes.
        These should be prioritized.
        """
        # Count how many nodes each node is blocking (directly or transitively)
        blocking_counts = {}

        for node in self.nodes.values():
            if node.status == CompletionStatus.COMPLETED:
                continue
            blocking_counts[node.id] = len(self._get_transitive_dependents(node.id))

        # Sort by blocking count
        sorted_nodes = sorted(
            blocking_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [self.get_node(nid) for nid, _ in sorted_nodes[:10] if self.get_node(nid)]

    def _get_transitive_dependents(self, node_id: str, visited: set = None) -> set:
        """Get all nodes that transitively depend on this node."""
        if visited is None:
            visited = set()

        if node_id in visited:
            return set()

        visited.add(node_id)
        dependents = set()

        for dep in self.get_dependents(node_id):
            dependents.add(dep.id)
            dependents.update(self._get_transitive_dependents(dep.id, visited))

        return dependents

    def merge_duplicate_nodes(self, node_id_1: str, node_id_2: str) -> Optional[Node]:
        """
        Merge two nodes that represent the same requirement.
        Keeps node_1, transfers all edges from node_2 to node_1.
        """
        node1 = self.get_node(node_id_1)
        node2 = self.get_node(node_id_2)

        if not node1 or not node2:
            return None

        # Transfer incoming edges
        for edge in self.get_incoming_edges(node_id_2):
            edge.target_id = node_id_1
            if node_id_1 not in self._reverse_adjacency:
                self._reverse_adjacency[node_id_1] = []
            self._reverse_adjacency[node_id_1].append(edge.id)

        # Transfer outgoing edges
        for edge in self.get_outgoing_edges(node_id_2):
            edge.source_id = node_id_1
            if node_id_1 not in self._adjacency:
                self._adjacency[node_id_1] = []
            self._adjacency[node_id_1].append(edge.id)

        # Merge metadata
        node1.tags = list(set(node1.tags + node2.tags))
        node1.metadata.update(node2.metadata)
        if node2.source_text and not node1.source_text:
            node1.source_text = node2.source_text

        # Remove node2
        del self.nodes[node_id_2]
        del self._adjacency[node_id_2]
        del self._reverse_adjacency[node_id_2]

        return node1

    def to_dict(self) -> dict:
        """Serialize the graph to a dictionary."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the graph to JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "RequirementGraph":
        """Deserialize a graph from a dictionary."""
        graph = cls()
        for node_data in data.get("nodes", []):
            graph.add_node(Node.from_dict(node_data))
        for edge_data in data.get("edges", []):
            graph.add_edge(Edge.from_dict(edge_data))
        return graph

    @classmethod
    def from_json(cls, json_str: str) -> "RequirementGraph":
        """Deserialize a graph from JSON."""
        return cls.from_dict(json.loads(json_str))

    def save(self, path: str):
        """Save the graph to a file."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "RequirementGraph":
        """Load a graph from a file."""
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_json(f.read())

    def __repr__(self) -> str:
        return f"RequirementGraph(nodes={len(self.nodes)}, edges={len(self.edges)})"
