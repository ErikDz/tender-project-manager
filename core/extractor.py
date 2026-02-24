"""
AI-Powered Requirement Extractor

Uses the LLM to analyze documents and extract requirements, conditions,
checkboxes, signatures, etc. into the requirement graph.
"""

import json
import time
from typing import Optional
from dataclasses import dataclass

from .graph import RequirementGraph, NodeType, EdgeType, CompletionStatus
from .document_reader import DocumentContent
from .logging_config import get_logger

logger = get_logger("extractor")


@dataclass
class ExtractionResult:
    """Result of extracting requirements from a document."""
    document_path: str
    nodes_created: list[str]  # Node IDs
    edges_created: list[str]  # Edge IDs
    raw_extraction: dict      # Raw LLM output
    error: Optional[str] = None


# JSON Schema for structured response - Flattened to avoid nesting depth limits
EXTRACTION_SCHEMA = {
    "name": "tender_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "document_summary": {
                "type": "string",
                "description": "Brief description of what this document is"
            },
            "document_type": {
                "type": "string",
                "enum": ["checklist", "form", "contract", "declaration", "instruction", "other"],
                "description": "Type of document"
            },
            "items": {
                "type": "array",
                "description": "List of extracted requirements, checkboxes, signatures, etc.",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_type": {
                            "type": "string",
                            "enum": ["document", "requirement", "condition", "checkbox", "signature", "field", "attachment", "deadline"],
                            "description": "Type of extracted item"
                        },
                        "title": {
                            "type": "string",
                            "description": "Short descriptive title"
                        },
                        "description": {
                            "type": "string",
                            "description": "Full description of the requirement"
                        },
                        "source_text": {
                            "type": "string",
                            "description": "Original German text this was extracted from"
                        },
                        "source_location": {
                            "type": "string",
                            "description": "Page/section reference if available"
                        },
                        "is_required": {
                            "type": "boolean",
                            "description": "Whether this item is required (true) or optional (false)"
                        },
                        "is_checked": {
                            "type": "boolean",
                            "description": "For checkboxes: true if checked, false if unchecked or not a checkbox"
                        },
                        "deadline_date": {
                            "type": "string",
                            "description": "ISO date string if there's a deadline, empty string otherwise"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0-1"
                        },
                        "tags_csv": {
                            "type": "string",
                            "description": "Comma-separated tags"
                        },
                        "requires_item": {
                            "type": "string",
                            "description": "Title of item this requires (empty if none)"
                        },
                        "conditional_on_item": {
                            "type": "string",
                            "description": "Title of condition this depends on (empty if none)"
                        }
                    },
                    "required": ["item_type", "title", "description", "source_text", "source_location", "is_required", "is_checked", "deadline_date", "confidence", "tags_csv", "requires_item", "conditional_on_item"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["document_summary", "document_type", "items"],
        "additionalProperties": False
    }
}


EXTRACTION_PROMPT = """You are analyzing a German tender (Vergabe/Ausschreibung) document to extract all requirements, conditions, and actions needed for submission.

DOCUMENT PATH: {document_path}
DOCUMENT NAME: {document_name}

DOCUMENT CONTENT:
{document_content}

---

Analyze this document and extract ALL of the following:

1. **DOCUMENTS** - Physical documents that must be submitted
   - Look for: Anlagen, Nachweise, Formulare, Erklärungen, Bescheinigungen
   - Note if they are marked as required (×, ⊠, x) or optional (☐)

2. **REQUIREMENTS** - Things that must be done or provided
   - Deadlines, certifications needed, qualifications required
   - Actions to take ("einzureichen", "vorzulegen", "nachzuweisen")

3. **CONDITIONS** - Conditional clauses that affect what's required
   - Look for: "wenn", "falls", "sofern", "im Falle", "bei"
   - These create dependencies - if condition X, then requirement Y applies

4. **CHECKBOXES** - Specific checkboxes to be checked
   - Checked: × ⊠ x [x] ✓ ✔
   - Unchecked: ☐ [ ] □
   - Note the context of what checking means

5. **SIGNATURES** - Where signatures are required
   - Look for: "Unterschrift", "rechtsverbindlich", "zu unterzeichnen"
   - Note type: qualified electronic, advanced electronic, or handwritten

6. **FIELDS** - Form fields that need to be filled
   - Company name, address, contact details
   - Prices, quantities, dates
   - References, certifications numbers

7. **ATTACHMENTS** - Files/documents to attach
   - Certificates, proof documents, plans
   - Note required format if specified

8. **DEADLINES** - Time-based requirements
   - Submission deadline (Abgabefrist)
   - Validity periods (Bindefrist)
   - Document validity dates

Important:
- Extract EVERYTHING, even if it seems minor
- Preserve original German terms in source_text
- Be specific about what exactly is required
- For conditions, clearly state the trigger and consequence
- For checkboxes, note current state (checked/unchecked) if visible
- Identify critical items that cause exclusion if missing (Ausschlusskriterium)
- Set is_required=true for mandatory items, false for optional
- Use confidence between 0.0 and 1.0 based on how certain you are
"""


class RequirementExtractor:
    """
    Extracts requirements from documents using AI.

    The extractor processes documents one by one, adding to an evolving
    requirement graph. It identifies connections between items both within
    and across documents.
    """

    def __init__(self, openai_client, model: str = "google/gemini-3-flash-preview"):
        self.client = openai_client
        self.model = model
        self.processed_documents: set[str] = set()
        logger.info(f"Initialized RequirementExtractor with model: {model}")

    def extract(
        self,
        document: DocumentContent,
        graph: RequirementGraph,
        max_content_length: int = 50000
    ) -> ExtractionResult:
        """Extract requirements from a document and add to the graph."""
        logger.info(f"Extracting requirements from: {document.filename}")

        if document.error or not document.is_successful:
            logger.warning(f"Skipping document with error: {document.error}")
            return ExtractionResult(
                document_path=document.path,
                nodes_created=[],
                edges_created=[],
                raw_extraction={},
                error=document.error or "No content extracted"
            )

        # Truncate very long documents
        content = document.text
        original_length = len(content)
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[... content truncated ...]"
            logger.debug(f"Truncated content from {original_length} to {max_content_length} chars")

        # Build the prompt
        prompt = EXTRACTION_PROMPT.format(
            document_path=document.path,
            document_name=document.filename,
            document_content=content
        )
        logger.debug(f"Built prompt with {len(prompt)} chars")

        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 2.0
        last_error = None
        response_text = None

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{max_retries} for {document.filename}")
                    time.sleep(retry_delay * (2 ** (attempt - 1)))  # Exponential backoff

                logger.debug(f"Calling LLM API ({self.model})...")
                start_time = time.time()

                # Use structured response with JSON schema
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={
                        "type": "json_schema",
                        "json_schema": EXTRACTION_SCHEMA
                    }
                )

                elapsed = time.time() - start_time
                logger.debug(f"LLM API call completed in {elapsed:.2f}s")

                # Check for empty/None response
                if response is None:
                    raise ValueError("API returned None response")
                if not hasattr(response, 'choices') or response.choices is None:
                    raise ValueError("API response has no choices")
                if len(response.choices) == 0:
                    raise ValueError("API response has empty choices list")
                if response.choices[0].message is None:
                    raise ValueError("API response message is None")
                if response.choices[0].message.content is None:
                    raise ValueError("API response content is None")

                response_text = response.choices[0].message.content
                logger.debug(f"Response length: {len(response_text)} chars")

                extraction = json.loads(response_text)
                logger.debug(f"Parsed {len(extraction.get('items', []))} items from response")

                # Success - break out of retry loop
                break

            except json.JSONDecodeError as e:
                last_error = f"Failed to parse LLM response as JSON: {e}"
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logger.error(last_error)
                    return ExtractionResult(
                        document_path=document.path,
                        nodes_created=[],
                        edges_created=[],
                        raw_extraction={"raw_response": response_text or ""},
                        error=last_error
                    )

            except ValueError as e:
                # Empty response - retry
                last_error = f"Empty API response: {e}"
                logger.warning(f"Empty response (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"LLM API returned empty response after {max_retries} attempts")
                    return ExtractionResult(
                        document_path=document.path,
                        nodes_created=[],
                        edges_created=[],
                        raw_extraction={},
                        error=last_error
                    )

            except Exception as e:
                last_error = f"LLM API error: {e}"
                error_str = str(e).lower()

                # Check if it's a retryable error
                retryable = any(x in error_str for x in [
                    'rate limit', 'timeout', 'connection', 'temporary',
                    '429', '500', '502', '503', '504', 'overloaded'
                ])

                if retryable and attempt < max_retries - 1:
                    logger.warning(f"Retryable error (attempt {attempt + 1}): {e}")
                    continue

                logger.exception(f"LLM API error for {document.filename}")
                return ExtractionResult(
                    document_path=document.path,
                    nodes_created=[],
                    edges_created=[],
                    raw_extraction={},
                    error=last_error
                )

        # Process extraction into graph
        nodes_created = []
        edges_created = []
        title_to_node: dict[str, str] = {}  # Map titles to node IDs for relationship linking

        # Create nodes for each extracted item
        for item in extraction.get("items", []):
            # Use item_type from flattened schema
            node_type = self._map_item_type(item.get("item_type", "requirement"))

            # Parse tags from CSV string
            tags_csv = item.get("tags_csv", "")
            tags = [t.strip() for t in tags_csv.split(",") if t.strip()] if tags_csv else []

            node = graph.create_node(
                type=node_type,
                title=item.get("title", "Untitled"),
                description=item.get("description", ""),
                source_document=document.path,
                source_location=item.get("source_location"),
                source_text=item.get("source_text"),
                confidence=item.get("confidence", 0.8),
                tags=tags,
                metadata={
                    "is_required": item.get("is_required", True),
                    "document_type": extraction.get("document_type"),
                }
            )

            # Handle checkbox state (is_checked is boolean in flattened schema)
            if node_type == NodeType.CHECKBOX:
                is_checked = item.get("is_checked", False)
                node.checkbox_state = is_checked
                if is_checked:
                    node.status = CompletionStatus.COMPLETED

            # Handle deadline (deadline_date is string in flattened schema)
            deadline_str = item.get("deadline_date", "")
            if deadline_str and deadline_str.strip():
                try:
                    from datetime import datetime
                    node.deadline = datetime.fromisoformat(deadline_str)
                except:
                    node.metadata["deadline_raw"] = deadline_str

            nodes_created.append(node.id)
            title_to_node[item.get("title", "").lower()] = node.id

        # Create edges for relationships (from flattened schema)
        for item in extraction.get("items", []):
            source_title = item.get("title", "").lower()
            source_id = title_to_node.get(source_title)

            if not source_id:
                continue

            # Handle requires_item relationship
            requires_item = item.get("requires_item", "")
            if requires_item and requires_item.strip():
                target_title = requires_item.strip().lower()
                target_id = title_to_node.get(target_title)

                # Also search existing graph for target
                if not target_id:
                    existing = graph.find_nodes(requires_item.strip())
                    if existing:
                        target_id = existing[0].id

                if target_id and target_id != source_id:
                    edge = graph.connect(
                        source_id=source_id,
                        target_id=target_id,
                        type=EdgeType.REQUIRES,
                        description=f"{item.get('title')} requires {requires_item}",
                    )
                    edges_created.append(edge.id)

            # Handle conditional_on_item relationship
            conditional_on = item.get("conditional_on_item", "")
            if conditional_on and conditional_on.strip():
                target_title = conditional_on.strip().lower()
                target_id = title_to_node.get(target_title)

                # Also search existing graph for target
                if not target_id:
                    existing = graph.find_nodes(conditional_on.strip())
                    if existing:
                        target_id = existing[0].id

                if target_id and target_id != source_id:
                    edge = graph.connect(
                        source_id=source_id,
                        target_id=target_id,
                        type=EdgeType.CONDITIONAL_ON,
                        description=f"{item.get('title')} conditional on {conditional_on}",
                    )
                    edges_created.append(edge.id)

        self.processed_documents.add(document.path)

        logger.info(f"Extracted from {document.filename}: {len(nodes_created)} nodes, {len(edges_created)} edges")

        return ExtractionResult(
            document_path=document.path,
            nodes_created=nodes_created,
            edges_created=edges_created,
            raw_extraction=extraction,
        )

    def _map_item_type(self, type_str: str) -> NodeType:
        """Map string type to NodeType enum."""
        mapping = {
            "document": NodeType.DOCUMENT,
            "requirement": NodeType.REQUIREMENT,
            "condition": NodeType.CONDITION,
            "checkbox": NodeType.CHECKBOX,
            "signature": NodeType.SIGNATURE,
            "field": NodeType.FIELD,
            "attachment": NodeType.ATTACHMENT,
            "deadline": NodeType.DEADLINE,
        }
        return mapping.get(type_str.lower(), NodeType.REQUIREMENT)

    def _map_relationship_type(self, type_str: str) -> EdgeType:
        """Map string relationship to EdgeType enum."""
        mapping = {
            "requires": EdgeType.REQUIRES,
            "required_by": EdgeType.REQUIRED_BY,
            "conditional_on": EdgeType.CONDITIONAL_ON,
            "triggers": EdgeType.TRIGGERS,
            "part_of": EdgeType.PART_OF,
            "references": EdgeType.REFERENCES,
            "depends_on": EdgeType.DEPENDS_ON,
            "mutually_exclusive": EdgeType.MUTUALLY_EXCLUSIVE,
        }
        return mapping.get(type_str.lower(), EdgeType.REFERENCES)

    def process_directory(
        self,
        documents: list[DocumentContent],
        graph: Optional[RequirementGraph] = None,
        progress_callback: Optional[callable] = None
    ) -> tuple[RequirementGraph, list[ExtractionResult]]:
        """
        Process all documents in a directory and build the requirement graph.

        Args:
            documents: List of DocumentContent objects to process
            graph: Existing graph to add to, or None to create new
            progress_callback: Optional callback(current, total, document_name)

        Returns:
            Tuple of (graph, list of extraction results)
        """
        if graph is None:
            graph = RequirementGraph()
            logger.debug("Created new RequirementGraph")

        results = []
        total = len(documents)
        logger.info(f"Processing {total} documents...")

        start_time = time.time()

        for i, doc in enumerate(documents):
            logger.info(f"[{i+1}/{total}] Processing: {doc.filename}")
            if progress_callback:
                progress_callback(i + 1, total, doc.filename)

            result = self.extract(doc, graph)
            results.append(result)

            if result.error:
                logger.warning(f"  Error: {result.error}")
            else:
                logger.debug(f"  Created {len(result.nodes_created)} nodes, {len(result.edges_created)} edges")

        # After processing all documents, try to resolve placeholder references
        logger.debug("Resolving placeholder references...")
        self._resolve_placeholders(graph)

        elapsed = time.time() - start_time
        successful = len([r for r in results if not r.error])
        logger.info(f"Processing complete: {successful}/{total} documents in {elapsed:.1f}s")
        logger.info(f"Graph now has {len(graph.nodes)} nodes and {len(graph.edges)} edges")

        return graph, results

    def _resolve_placeholders(self, graph: RequirementGraph):
        """
        Try to match placeholder document nodes with actual document nodes.
        """
        placeholders = [n for n in graph.nodes.values() if "placeholder" in n.tags]
        real_docs = [n for n in graph.nodes.values()
                     if n.type == NodeType.DOCUMENT and "placeholder" not in n.tags]

        for placeholder in placeholders:
            # Try to find a matching real document
            placeholder_name = placeholder.title.lower()

            for doc in real_docs:
                doc_name = doc.title.lower()
                # Check for partial matches
                if (placeholder_name in doc_name or
                    doc_name in placeholder_name or
                    self._fuzzy_match(placeholder_name, doc_name)):
                    # Merge the nodes
                    graph.merge_duplicate_nodes(doc.id, placeholder.id)
                    break

    def _fuzzy_match(self, str1: str, str2: str, threshold: float = 0.6) -> bool:
        """Simple fuzzy string matching."""
        # Normalize
        s1 = set(str1.lower().split())
        s2 = set(str2.lower().split())

        if not s1 or not s2:
            return False

        # Jaccard similarity
        intersection = len(s1 & s2)
        union = len(s1 | s2)

        return (intersection / union) >= threshold


class IncrementalExtractor:
    """
    Manages incremental extraction as documents are added.

    Tracks what has been processed and handles updates when
    documents change.
    """

    def __init__(self, extractor: RequirementExtractor):
        self.extractor = extractor
        self.document_hashes: dict[str, str] = {}  # path -> content hash
        logger.debug("Initialized IncrementalExtractor")

    def _hash_content(self, content: str) -> str:
        """Generate a hash of document content."""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()

    def process_new_or_changed(
        self,
        documents: list[DocumentContent],
        graph: RequirementGraph
    ) -> list[ExtractionResult]:
        """
        Process only new or changed documents.

        Returns list of extraction results for processed documents.
        """
        results = []
        skipped = 0
        changed = 0
        new = 0

        logger.info(f"Checking {len(documents)} documents for changes...")

        for doc in documents:
            content_hash = self._hash_content(doc.text)

            # Check if document is new or changed
            if doc.path in self.document_hashes:
                if self.document_hashes[doc.path] == content_hash:
                    logger.debug(f"Unchanged: {doc.filename}")
                    skipped += 1
                    continue

                # Document changed - remove old nodes and reprocess
                logger.info(f"Document changed: {doc.filename}")
                old_nodes = graph.get_nodes_by_document(doc.path)
                logger.debug(f"Removing {len(old_nodes)} old nodes from changed document")
                for node in old_nodes:
                    del graph.nodes[node.id]
                changed += 1
            else:
                logger.debug(f"New document: {doc.filename}")
                new += 1

            # Process the document
            result = self.extractor.extract(doc, graph)
            results.append(result)

            # Update hash
            self.document_hashes[doc.path] = content_hash

        logger.info(f"Incremental processing: {new} new, {changed} changed, {skipped} unchanged")

        return results
