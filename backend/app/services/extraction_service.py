"""Extraction service — wraps core extraction pipeline for web use."""

import os
import tempfile
from datetime import datetime, timezone

from core.document_reader import DocumentReader
from core.extractor import RequirementExtractor
from core.logging_config import get_logger
from ai.llm import openai_client, LLM_MODEL
from .graph_service import GraphService

logger = get_logger("extraction_service")


class ExtractionService:
    """Runs the AI extraction pipeline, writing results to Supabase."""

    def __init__(self, supabase_client):
        self.db = supabase_client
        self.reader = DocumentReader()
        self.extractor = RequirementExtractor(openai_client, model=LLM_MODEL)
        self.graph_service = GraphService(supabase_client)

    def run_extraction(self, project_id: str, job_id: str, force_full: bool = False):
        """Run extraction for all documents in a project.

        This method is designed to run in a background thread.
        Updates processing_jobs table with progress.
        """
        try:
            self._update_job(job_id, status="running", started_at=datetime.now(timezone.utc).isoformat())

            # Get all documents for this project
            docs = self.db.table("documents") \
                .select("*") \
                .eq("project_id", project_id) \
                .execute()

            total = len(docs.data)
            self._update_job(job_id, total_documents=total)

            if total == 0:
                self._update_job(job_id, status="completed", completed_at=datetime.now(timezone.utc).isoformat())
                return

            # Load existing graph (or create new)
            graph = self.graph_service.load_graph(project_id)

            # Build document ID map (filename -> UUID)
            doc_id_map = {}
            processed = 0
            errors = []

            for doc_row in docs.data:
                try:
                    self._update_job(
                        job_id,
                        current_step=f"Processing: {doc_row['filename']}",
                        processed_documents=processed,
                        progress=processed / total,
                    )

                    # Skip if already processed and not force_full
                    if not force_full and doc_row.get("content_hash"):
                        existing_nodes = self.db.table("nodes") \
                            .select("id") \
                            .eq("document_id", doc_row["id"]) \
                            .execute()
                        if existing_nodes.data:
                            processed += 1
                            continue

                    # Download from Supabase Storage to temp file
                    content = self._download_document(doc_row)
                    if not content:
                        errors.append(f"Failed to download: {doc_row['filename']}")
                        processed += 1
                        continue

                    # Extract requirements using AI
                    result = self.extractor.extract(content, graph)

                    # Map this document filename to its UUID
                    doc_id_map[doc_row["filename"]] = doc_row["id"]

                    # Update content hash
                    import hashlib
                    text_hash = hashlib.md5(content.text.encode()).hexdigest()
                    self.db.table("documents") \
                        .update({"content_hash": text_hash, "extracted_text": content.text[:50000]}) \
                        .eq("id", doc_row["id"]) \
                        .execute()

                except Exception as e:
                    logger.error(f"Error processing {doc_row['filename']}: {e}")
                    errors.append(f"{doc_row['filename']}: {str(e)}")

                processed += 1

            # Resolve cross-document placeholder references
            self.extractor._resolve_placeholders(graph)

            # Save the complete graph to DB
            self.graph_service.save_graph(project_id, graph, doc_id_map)

            # Mark job complete
            error_msg = "; ".join(errors) if errors else None
            self._update_job(
                job_id,
                status="completed",
                progress=1.0,
                processed_documents=total,
                current_step="Done",
                error_message=error_msg,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(f"Extraction complete for project {project_id}: "
                        f"{len(graph.nodes)} nodes, {len(graph.edges)} edges, {len(errors)} errors")

        except Exception as e:
            logger.error(f"Extraction failed for project {project_id}: {e}")
            self._update_job(
                job_id,
                status="failed",
                error_message=str(e),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    def _download_document(self, doc_row):
        """Download a document from Supabase Storage and read its content."""
        try:
            storage_path = doc_row["storage_path"]
            file_bytes = self.db.storage.from_("documents").download(storage_path)

            # Write to temp file for DocumentReader
            suffix = os.path.splitext(doc_row["filename"])[1]
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                from core.document_reader import read_document
                content = read_document(tmp_path)
                # Override temp path with original filename so nodes get correct source_document
                content.path = doc_row["filename"]
                content.filename = doc_row["filename"]
                return content
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"Failed to download {doc_row['filename']}: {e}")
            return None

    def _update_job(self, job_id: str, **kwargs):
        """Update processing job fields."""
        self.db.table("processing_jobs") \
            .update(kwargs) \
            .eq("id", job_id) \
            .execute()
