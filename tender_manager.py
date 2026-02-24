"""
Tender Project Manager

Main application that processes tender documents and manages requirements.
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ai.llm import openai_client
from core.logging_config import setup_logging, get_logger
from core.graph import RequirementGraph, CompletionStatus
from core.document_reader import DocumentReader, read_all_documents
from core.extractor import RequirementExtractor, IncrementalExtractor
from core.todo import TodoGenerator

logger = get_logger("manager")


class TenderProject:
    """
    Manages a single tender project.

    A tender project consists of:
    - A directory of tender documents
    - A requirement graph built from those documents
    - A to-do list derived from the graph
    """

    def __init__(self, tender_directory: str, project_name: Optional[str] = None):
        self.tender_directory = Path(tender_directory).resolve()
        self.project_name = project_name or self.tender_directory.name

        logger.info(f"Initializing TenderProject: {self.project_name}")
        logger.debug(f"Tender directory: {self.tender_directory}")

        # State directory for saving graph, etc.
        self.state_dir = self.tender_directory / ".tender_state"
        self.state_dir.mkdir(exist_ok=True)
        logger.debug(f"State directory: {self.state_dir}")

        self.graph_path = self.state_dir / "requirement_graph.json"
        self.log_path = self.state_dir / "tender.log"

        # Initialize components
        logger.debug("Initializing components...")
        self.reader = DocumentReader()
        self.extractor = RequirementExtractor(openai_client)
        self.incremental = IncrementalExtractor(self.extractor)

        # Load or create graph
        if self.graph_path.exists():
            logger.info(f"Loading existing graph from {self.graph_path}")
            self.graph = RequirementGraph.load(str(self.graph_path))
            logger.info(f"Loaded graph with {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")
        else:
            logger.info("Creating new requirement graph")
            self.graph = RequirementGraph()

    def extract_archives(self) -> list[str]:
        """Extract any ZIP archives in the tender directory."""
        logger.info("Checking for ZIP archives to extract...")
        extracted = self.reader.extract_archives(str(self.tender_directory))
        if extracted:
            logger.info(f"Extracted {len(extracted)} archives")
            for path in extracted:
                logger.debug(f"  Extracted: {path}")
        else:
            logger.debug("No new archives to extract")
        return extracted

    def scan_documents(self) -> list:
        """Scan all documents in the tender directory."""
        logger.info(f"Scanning documents in {self.tender_directory}")

        # First extract any archives
        self.extract_archives()

        # Read all documents
        logger.debug("Reading all documents...")
        documents = read_all_documents(str(self.tender_directory), extract_archives=True)

        successful = [d for d in documents if d.is_successful]
        failed = [d for d in documents if not d.is_successful]

        logger.info(f"Scan complete: {len(documents)} total, {len(successful)} successful, {len(failed)} failed")

        if failed:
            logger.warning(f"Failed to read {len(failed)} documents:")
            for doc in failed[:10]:
                logger.warning(f"  {doc.filename}: {doc.error}")
            if len(failed) > 10:
                logger.warning(f"  ... and {len(failed) - 10} more")

        return documents

    def process_documents(
        self,
        documents: Optional[list] = None,
        incremental: bool = True
    ) -> list:
        """
        Process documents and build/update the requirement graph.

        Args:
            documents: List of DocumentContent objects, or None to scan directory
            incremental: If True, only process new/changed documents

        Returns:
            List of ExtractionResult objects
        """
        logger.info(f"Starting document processing (incremental={incremental})")

        if documents is None:
            documents = self.scan_documents()

        # Filter to successful documents
        all_count = len(documents)
        documents = [d for d in documents if d.is_successful]
        logger.debug(f"Filtered to {len(documents)} successful documents (from {all_count})")

        if not documents:
            logger.warning("No documents to process")
            return []

        logger.info(f"Processing {len(documents)} documents with AI...")

        def progress(current, total, name):
            logger.info(f"[{current}/{total}] Processing: {name}")

        if incremental:
            logger.debug("Using incremental extraction")
            results = self.incremental.process_new_or_changed(documents, self.graph)
        else:
            logger.debug("Using full extraction")
            self.graph, results = self.extractor.process_directory(
                documents,
                self.graph,
                progress_callback=progress
            )

        # Save the graph
        self.save()

        # Summary
        nodes_created = sum(len(r.nodes_created) for r in results)
        edges_created = sum(len(r.edges_created) for r in results)
        errors = [r for r in results if r.error]

        logger.info(f"Extraction complete: {nodes_created} nodes, {edges_created} edges created")
        if errors:
            logger.warning(f"{len(errors)} documents had errors:")
            for err in errors[:5]:
                logger.warning(f"  {Path(err.document_path).name}: {err.error}")

        return results

    def save(self):
        """Save the current state."""
        logger.debug(f"Saving graph to {self.graph_path}")
        self.graph.save(str(self.graph_path))
        logger.info(f"Graph saved ({len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges)")

    def get_todo(self) -> TodoGenerator:
        """Get a to-do list generator for this project."""
        return TodoGenerator(self.graph)

    def print_summary(self):
        """Print a summary of the project status."""
        stats = self.graph.get_completion_stats()
        todo = self.get_todo()
        summary = todo.get_summary()

        print(f"\n{'='*60}")
        print(f"TENDER PROJECT: {self.project_name}")
        print(f"{'='*60}")
        print(f"\nGraph Statistics:")
        print(f"  - Total nodes: {stats['total_nodes']}")
        print(f"  - Total edges: {len(self.graph.edges)}")
        print(f"\nCompletion Status:")
        for status, count in stats['by_status'].items():
            if count > 0:
                print(f"  - {status}: {count}")
        print(f"\nOverall Progress: {stats['completion_percentage']}%")
        print(f"\nCritical Items: {summary['critical_items']} ({summary['critical_completed']} done)")
        print(f"Ready to Work On: {summary['actionable_now']}")

        logger.debug(f"Summary displayed: {stats}")

    def print_todo(self, category: Optional[str] = None, show_all: bool = False):
        """Print the to-do list."""
        todo = self.get_todo()
        logger.debug(f"Printing todo list (category={category}, show_all={show_all})")

        if category == "critical":
            items = todo.get_critical_items()
            print(f"\n=== Critical Items ({len(items)}) ===\n")
            for item in items:
                status = "✓" if item.status == CompletionStatus.COMPLETED else "○"
                print(f"{status} {item.title}")
                if item.description:
                    print(f"   {item.description[:80]}...")
                print()

        elif category == "actionable":
            items = todo.get_actionable_now()
            print(f"\n=== Ready to Work On ({len(items)}) ===\n")
            for item in items[:20]:
                print(f"○ [{item.priority.name}] {item.title}")
                if item.source_document:
                    print(f"   Source: {Path(item.source_document).name}")
                print()

        else:
            # Full to-do list
            categories = todo.generate()
            for cat in categories:
                if not show_all and cat.completed_count == cat.total_count:
                    continue  # Skip completed categories

                print(f"\n=== {cat.name} ({cat.completed_count}/{cat.total_count}) ===\n")
                for item in cat.items:
                    if not show_all and item.status == CompletionStatus.COMPLETED:
                        continue
                    status = "✓" if item.status == CompletionStatus.COMPLETED else "○"
                    priority = "!" if item.priority.value <= 2 else " "
                    print(f"{status}{priority} {item.title}")
                    if item.blocked_by:
                        print(f"    ⏸️ Blocked by: {', '.join(item.blocked_by[:2])}")

    def mark_complete(self, search_term: str) -> bool:
        """Mark an item as complete by searching for it."""
        logger.info(f"Searching for item to mark complete: '{search_term}'")
        nodes = self.graph.find_nodes(search_term)

        if not nodes:
            logger.warning(f"No items found matching '{search_term}'")
            print(f"No items found matching '{search_term}'")
            return False

        if len(nodes) > 1:
            logger.info(f"Multiple items found matching '{search_term}': {len(nodes)}")
            print(f"Multiple items found matching '{search_term}':")
            for i, node in enumerate(nodes[:5]):
                print(f"  {i+1}. {node.title}")
            return False

        node = nodes[0]
        logger.info(f"Marking as complete: {node.title} (id={node.id})")
        self.graph.update_status(node.id, CompletionStatus.COMPLETED)
        self.save()
        print(f"Marked as complete: {node.title}")
        return True

    def export_todo_markdown(self, output_path: Optional[str] = None) -> str:
        """Export the to-do list as markdown."""
        todo = self.get_todo()
        markdown = todo.to_markdown()

        if output_path is None:
            output_path = str(self.state_dir / "todo.md")

        logger.info(f"Exporting todo list to {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"To-do list exported to {output_path}")
        return output_path


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Tender Project Manager - AI-powered tender document analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s path/to/tender --scan        Scan and list all documents
  %(prog)s path/to/tender --process     Process documents with AI
  %(prog)s path/to/tender --todo        Show to-do list
  %(prog)s path/to/tender --critical    Show critical items only
  %(prog)s path/to/tender --export      Export to-do as markdown
        """
    )
    parser.add_argument("directory", help="Path to tender documents directory")
    parser.add_argument("--scan", action="store_true", help="Scan documents without processing")
    parser.add_argument("--process", action="store_true", help="Process documents with AI")
    parser.add_argument("--full", action="store_true", help="Force full reprocessing")
    parser.add_argument("--todo", action="store_true", help="Show to-do list")
    parser.add_argument("--critical", action="store_true", help="Show critical items only")
    parser.add_argument("--actionable", action="store_true", help="Show actionable items only")
    parser.add_argument("--export", action="store_true", help="Export to-do as markdown")
    parser.add_argument("--complete", type=str, help="Mark an item as complete")
    parser.add_argument("--summary", action="store_true", help="Show project summary")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging based on verbosity
    if args.debug:
        log_level = "DEBUG"
    elif args.verbose:
        log_level = "INFO"
    else:
        log_level = "WARNING"

    # Setup logging
    setup_logging(
        level=log_level,
        log_file=str(Path(args.directory).resolve() / ".tender_state" / "tender.log")
    )

    logger.info(f"Starting Tender Manager (log_level={log_level})")
    logger.debug(f"Arguments: {args}")

    project = TenderProject(args.directory)

    if args.scan:
        project.scan_documents()

    elif args.process:
        project.process_documents(incremental=not args.full)
        project.print_summary()

    elif args.complete:
        project.mark_complete(args.complete)

    elif args.export:
        project.export_todo_markdown()

    elif args.todo or args.critical or args.actionable:
        if args.critical:
            project.print_todo(category="critical")
        elif args.actionable:
            project.print_todo(category="actionable")
        else:
            project.print_todo()

    elif args.summary:
        project.print_summary()

    else:
        # Default: show summary if graph exists, otherwise scan
        if project.graph.nodes:
            project.print_summary()
        else:
            print("No existing analysis found. Run with --process to analyze documents.")
            project.scan_documents()

    logger.info("Tender Manager completed")


if __name__ == "__main__":
    main()
