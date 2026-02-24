"""
To-Do List Generator

Converts the requirement graph into actionable to-do lists,
prioritized and organized for human consumption.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum

from .graph import RequirementGraph, Node, NodeType, CompletionStatus


class Priority(Enum):
    CRITICAL = 1    # Missing = automatic disqualification
    HIGH = 2        # Required, but not immediate disqualification
    MEDIUM = 3      # Recommended or conditional
    LOW = 4         # Optional or nice-to-have


@dataclass
class TodoItem:
    """A single actionable to-do item."""
    id: str
    title: str
    description: str
    priority: Priority
    status: CompletionStatus
    category: str
    source_document: Optional[str] = None
    deadline: Optional[datetime] = None
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    node_id: str = ""  # Reference back to graph node
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "status": self.status.value,
            "category": self.category,
            "source_document": self.source_document,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "blocked_by": self.blocked_by,
            "blocks": self.blocks,
            "node_id": self.node_id,
            "tags": self.tags,
        }


@dataclass
class TodoCategory:
    """A category grouping related to-do items."""
    name: str
    description: str
    items: list[TodoItem] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def completed_count(self) -> int:
        return len([i for i in self.items if i.status == CompletionStatus.COMPLETED])

    @property
    def completion_percentage(self) -> float:
        if self.total_count == 0:
            return 100.0
        return round(self.completed_count / self.total_count * 100, 1)


class TodoGenerator:
    """
    Generates organized to-do lists from the requirement graph.
    """

    # Keywords that indicate critical/exclusion items
    CRITICAL_KEYWORDS = [
        "ausschluss", "zwingend", "muss", "pflicht", "erforderlich",
        "unbedingt", "ausgeschlossen", "nicht berücksichtigt",
        "fehlen", "mangel", "ungültig", "disqualif"
    ]

    # Categories for organizing items
    CATEGORIES = {
        NodeType.DOCUMENT: "Documents to Submit",
        NodeType.SIGNATURE: "Signatures Required",
        NodeType.CHECKBOX: "Checkboxes to Complete",
        NodeType.FIELD: "Fields to Fill",
        NodeType.ATTACHMENT: "Attachments to Include",
        NodeType.REQUIREMENT: "Requirements to Meet",
        NodeType.DEADLINE: "Deadlines to Track",
        NodeType.CONDITION: "Conditions to Evaluate",
    }

    def __init__(self, graph: RequirementGraph):
        self.graph = graph

    def generate(self) -> list[TodoCategory]:
        """Generate a complete to-do list organized by category."""
        categories: dict[str, TodoCategory] = {}

        for node in self.graph.nodes.values():
            # Skip conditions that are just informational
            if node.type == NodeType.CONDITION and node.status == CompletionStatus.NOT_APPLICABLE:
                continue

            category_name = self.CATEGORIES.get(node.type, "Other")

            if category_name not in categories:
                categories[category_name] = TodoCategory(
                    name=category_name,
                    description=f"Items of type: {node.type.value}"
                )

            todo_item = self._node_to_todo(node)
            categories[category_name].items.append(todo_item)

        # Sort items within each category by priority, then by title
        for category in categories.values():
            category.items.sort(key=lambda x: (x.priority.value, x.title))

        # Sort categories by importance
        category_order = [
            "Documents to Submit",
            "Signatures Required",
            "Checkboxes to Complete",
            "Fields to Fill",
            "Attachments to Include",
            "Requirements to Meet",
            "Deadlines to Track",
            "Conditions to Evaluate",
            "Other",
        ]

        sorted_categories = []
        for name in category_order:
            if name in categories:
                sorted_categories.append(categories[name])

        # Add any remaining categories
        for name, category in categories.items():
            if name not in category_order:
                sorted_categories.append(category)

        return sorted_categories

    def _node_to_todo(self, node: Node) -> TodoItem:
        """Convert a graph node to a to-do item."""
        priority = self._determine_priority(node)

        # Get blocked_by and blocks relationships
        blocked_by = []
        blocks = []

        for dep in self.graph.get_dependencies(node.id):
            if dep.status != CompletionStatus.COMPLETED:
                blocked_by.append(dep.title)

        for dep in self.graph.get_dependents(node.id):
            if dep.status != CompletionStatus.COMPLETED:
                blocks.append(dep.title)

        return TodoItem(
            id=node.id,
            title=node.title,
            description=node.description,
            priority=priority,
            status=node.status,
            category=self.CATEGORIES.get(node.type, "Other"),
            source_document=node.source_document,
            deadline=node.deadline,
            blocked_by=blocked_by,
            blocks=blocks,
            node_id=node.id,
            tags=node.tags,
        )

    def _determine_priority(self, node: Node) -> Priority:
        """Determine the priority of a node based on its content and relationships."""
        # Check for critical keywords
        text_to_check = (
            (node.title or "") +
            (node.description or "") +
            (node.source_text or "")
        ).lower()

        for keyword in self.CRITICAL_KEYWORDS:
            if keyword in text_to_check:
                return Priority.CRITICAL

        # Check metadata
        if node.metadata.get("is_required") is True:
            return Priority.HIGH

        # Check node type
        if node.type == NodeType.SIGNATURE:
            return Priority.CRITICAL  # Signatures are usually critical
        if node.type == NodeType.DEADLINE:
            return Priority.CRITICAL
        if node.type == NodeType.DOCUMENT:
            return Priority.HIGH

        # Check if it blocks many other items
        dependents = self.graph.get_dependents(node.id)
        if len(dependents) >= 3:
            return Priority.HIGH

        # Conditional items are medium priority
        incoming_edges = self.graph.get_incoming_edges(node.id)
        for edge in incoming_edges:
            if edge.type.value == "conditional_on":
                return Priority.MEDIUM

        return Priority.MEDIUM

    def get_actionable_now(self) -> list[TodoItem]:
        """Get items that can be worked on right now (no blockers)."""
        actionable = []

        for node in self.graph.get_actionable_items():
            todo = self._node_to_todo(node)
            if not todo.blocked_by:
                actionable.append(todo)

        # Sort by priority
        actionable.sort(key=lambda x: (x.priority.value, x.title))
        return actionable

    def get_critical_items(self) -> list[TodoItem]:
        """Get all critical items that must be completed."""
        critical = []

        for node in self.graph.nodes.values():
            if node.status == CompletionStatus.COMPLETED:
                continue
            if node.status == CompletionStatus.NOT_APPLICABLE:
                continue

            todo = self._node_to_todo(node)
            if todo.priority == Priority.CRITICAL:
                critical.append(todo)

        critical.sort(key=lambda x: x.title)
        return critical

    def get_by_deadline(self) -> list[TodoItem]:
        """Get items sorted by deadline (earliest first)."""
        with_deadline = []

        for node in self.graph.nodes.values():
            if node.deadline and node.status != CompletionStatus.COMPLETED:
                todo = self._node_to_todo(node)
                with_deadline.append(todo)

        with_deadline.sort(key=lambda x: x.deadline or datetime.max)
        return with_deadline

    def get_summary(self) -> dict:
        """Get a summary of the to-do status."""
        categories = self.generate()

        total_items = sum(c.total_count for c in categories)
        completed_items = sum(c.completed_count for c in categories)

        critical = self.get_critical_items()
        critical_complete = len([c for c in critical if c.status == CompletionStatus.COMPLETED])

        return {
            "total_items": total_items,
            "completed_items": completed_items,
            "completion_percentage": round(completed_items / total_items * 100, 1) if total_items > 0 else 100,
            "critical_items": len(critical),
            "critical_completed": critical_complete,
            "actionable_now": len(self.get_actionable_now()),
            "categories": [
                {
                    "name": c.name,
                    "total": c.total_count,
                    "completed": c.completed_count,
                    "percentage": c.completion_percentage,
                }
                for c in categories
            ],
        }

    def to_markdown(self) -> str:
        """Generate a markdown representation of the to-do list."""
        categories = self.generate()
        summary = self.get_summary()

        lines = [
            "# Tender Requirements To-Do List",
            "",
            "## Summary",
            f"- **Total Items:** {summary['total_items']}",
            f"- **Completed:** {summary['completed_items']} ({summary['completion_percentage']}%)",
            f"- **Critical Items:** {summary['critical_items']} ({summary['critical_completed']} done)",
            f"- **Ready to Work On:** {summary['actionable_now']}",
            "",
        ]

        # Critical items section
        critical = self.get_critical_items()
        if critical:
            lines.extend([
                "## Critical Items (Must Complete)",
                "",
            ])
            for item in critical:
                status = "✅" if item.status == CompletionStatus.COMPLETED else "⚠️"
                lines.append(f"- {status} **{item.title}**")
                if item.description:
                    lines.append(f"  - {item.description[:100]}...")
            lines.append("")

        # Actionable items section
        actionable = self.get_actionable_now()
        if actionable:
            lines.extend([
                "## Ready to Work On Now",
                "",
            ])
            for item in actionable[:10]:  # Top 10
                lines.append(f"- [ ] **{item.title}** [{item.priority.name}]")
                if item.source_document:
                    lines.append(f"  - Source: {item.source_document}")
            lines.append("")

        # Categories
        for category in categories:
            lines.extend([
                f"## {category.name}",
                f"*{category.completed_count}/{category.total_count} completed ({category.completion_percentage}%)*",
                "",
            ])

            for item in category.items:
                checkbox = "x" if item.status == CompletionStatus.COMPLETED else " "
                priority_marker = "🔴" if item.priority == Priority.CRITICAL else (
                    "🟡" if item.priority == Priority.HIGH else "⚪"
                )
                lines.append(f"- [{checkbox}] {priority_marker} {item.title}")

                if item.blocked_by:
                    lines.append(f"  - ⏸️ Blocked by: {', '.join(item.blocked_by[:3])}")
                if item.deadline:
                    lines.append(f"  - 📅 Deadline: {item.deadline.strftime('%Y-%m-%d')}")

            lines.append("")

        return "\n".join(lines)
