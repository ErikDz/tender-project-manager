"""
Graph Visualization Tool

Generates visual representations of the requirement graph.
Shows source documents as parent nodes with extracted items as children.
"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from core.graph import RequirementGraph, NodeType, EdgeType, CompletionStatus


def generate_mermaid(graph: RequirementGraph, max_nodes_per_doc: int = None) -> str:
    """
    Generate a Mermaid flowchart diagram.
    Documents are shown as parent nodes containing their extracted items.
    If max_nodes_per_doc is None, shows ALL nodes.
    """
    lines = ["flowchart TB"]

    # Group nodes by source document
    by_document = defaultdict(list)
    for node in graph.nodes.values():
        if node.source_document:
            doc_name = Path(node.source_document).name
            by_document[doc_name].append(node)

    node_ids = {}  # Map original node IDs to safe mermaid IDs
    doc_ids = {}   # Map document names to safe mermaid IDs

    # Create subgraphs for each document
    for doc_idx, (doc_name, nodes) in enumerate(sorted(by_document.items(), key=lambda x: -len(x[1]))):
        doc_id = f"doc{doc_idx}"
        doc_ids[doc_name] = doc_id

        # Truncate document name for display
        display_name = doc_name[:35] + "..." if len(doc_name) > 35 else doc_name

        lines.append(f'    subgraph {doc_id}["{display_name}"]')

        # Add nodes for this document (all nodes if max_nodes_per_doc is None)
        nodes_to_show = nodes if max_nodes_per_doc is None else nodes[:max_nodes_per_doc]
        for node in nodes_to_show:
            safe_id = f"n{len(node_ids)}"
            node_ids[node.id] = safe_id

            # Truncate and escape title
            title = node.title[:30] + "..." if len(node.title) > 30 else node.title
            title = title.replace('"', "'").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")

            # Map node type to CSS class
            type_to_class = {
                "document": "docStyle",
                "requirement": "reqStyle",
                "field": "fieldStyle",
                "checkbox": "checkStyle",
                "signature": "sigStyle",
                "condition": "condStyle",
                "deadline": "deadlineStyle",
                "attachment": "attachStyle",
            }
            css_class = type_to_class.get(node.type.value, "reqStyle")

            # Node shape based on type
            node_type = node.type.value[0].upper()  # First letter
            if node.status == CompletionStatus.COMPLETED:
                lines.append(f'        {safe_id}["{node_type}: {title} ✓"]:::{css_class}')
            else:
                lines.append(f'        {safe_id}["{node_type}: {title}"]:::{css_class}')

        if max_nodes_per_doc is not None and len(nodes) > max_nodes_per_doc:
            lines.append(f'        {doc_id}_more["... +{len(nodes) - max_nodes_per_doc} more"]')

        lines.append("    end")

    # Add edges between nodes
    lines.append("")
    lines.append("    %% Relationships between requirements")
    for edge in graph.edges.values():
        if edge.source_id in node_ids and edge.target_id in node_ids:
            src = node_ids[edge.source_id]
            tgt = node_ids[edge.target_id]
            label = edge.type.value.replace("_", " ")
            lines.append(f"    {src} -.->|{label}| {tgt}")

    # Add styling - colors match the legend
    lines.append("")
    lines.append("    %% Styling - matches legend colors")
    lines.append("    classDef docStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b")
    lines.append("    classDef reqStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100")
    lines.append("    classDef fieldStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#7b1fa2")
    lines.append("    classDef checkStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#2e7d32")
    lines.append("    classDef sigStyle fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#c62828")
    lines.append("    classDef condStyle fill:#fffde7,stroke:#f57f17,stroke-width:2px,color:#f57f17")
    lines.append("    classDef deadlineStyle fill:#fce4ec,stroke:#ad1457,stroke-width:2px,color:#ad1457")
    lines.append("    classDef attachStyle fill:#e0f2f1,stroke:#00695c,stroke-width:2px,color:#00695c")

    return "\n".join(lines)


def generate_html_report(graph: RequirementGraph, output_path: str) -> str:
    """Generate an interactive HTML report with the graph."""

    # Collect statistics
    stats = graph.get_completion_stats()

    by_type = defaultdict(list)
    for node in graph.nodes.values():
        by_type[node.type.value].append(node)

    by_document = defaultdict(list)
    for node in graph.nodes.values():
        if node.source_document:
            doc_name = Path(node.source_document).name
            by_document[doc_name].append(node)

    # Generate Mermaid diagram (show ALL nodes - no limit)
    mermaid_code = generate_mermaid(graph, max_nodes_per_doc=None)

    # Build tabs HTML for types
    tabs_html = []
    content_html = []

    sorted_types = sorted(by_type.items(), key=lambda x: -len(x[1]))
    for i, (t, nodes) in enumerate(sorted_types):
        active = "active" if i == 0 else ""
        tabs_html.append(f'<button class="tab {active}" onclick="showTab(\'{t}\')">{t.title()} ({len(nodes)})</button>')

        items_html = []
        for n in nodes:
            status_class = "status-completed" if n.status == CompletionStatus.COMPLETED else "status-not_started"
            status_icon = "✓" if n.status == CompletionStatus.COMPLETED else "○"
            source = f"Source: {Path(n.source_document).name}" if n.source_document else ""
            conf = f" | Confidence: {n.confidence:.0%}" if n.confidence < 1 else ""

            items_html.append(f'''
            <div class="node-item">
                <div class="node-title">
                    <span class="{status_class}">{status_icon}</span>
                    {n.title}
                </div>
                <div class="node-meta">{source}{conf}</div>
            </div>
            ''')

        content_html.append(f'''
        <div id="tab-{t}" class="tab-content {active}">
            <div class="node-list">
                {"".join(items_html)}
            </div>
        </div>
        ''')

    # Build documents table with breakdown
    docs_html = []
    for doc, nodes in sorted(by_document.items(), key=lambda x: -len(x[1])):
        type_counts = defaultdict(int)
        for n in nodes:
            type_counts[n.type.value] += 1
        breakdown = ", ".join(f"{v} {k}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))
        docs_html.append(f'<tr><td>{doc}</td><td>{len(nodes)}</td><td style="font-size:12px;color:#666">{breakdown}</td></tr>')

    # Build type stats table
    type_stats_html = []
    for t, nodes in sorted_types:
        completed = len([n for n in nodes if n.status == CompletionStatus.COMPLETED])
        type_stats_html.append(f'<tr><td><span class="node-type type-{t}">{t.title()}</span></td><td>{len(nodes)}</td><td>{completed}</td></tr>')

    # Build edges table
    edges_html = []
    for edge in graph.edges.values():
        source_node = graph.get_node(edge.source_id)
        target_node = graph.get_node(edge.target_id)
        if source_node and target_node:
            edges_html.append(f'<tr><td>{source_node.title[:40]}</td><td><span class="edge-type">{edge.type.value}</span></td><td>{target_node.title[:40]}</td></tr>')

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tender Requirements Graph</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; margin-bottom: 20px; }}
        h2 {{ color: #555; margin: 20px 0 10px; border-bottom: 2px solid #ddd; padding-bottom: 5px; }}
        h3 {{ color: #666; margin: 15px 0 10px; font-size: 16px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-card h3 {{ color: #888; font-size: 14px; margin-bottom: 5px; }}
        .stat-card .value {{ font-size: 32px; font-weight: bold; color: #333; }}
        .stat-card .detail {{ font-size: 12px; color: #888; margin-top: 5px; }}
        .progress-bar {{ height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; margin-top: 10px; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #4caf50, #8bc34a); border-radius: 4px; }}
        .section {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .graph-container {{ position: relative; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
        .graph-wrapper {{ width: 100%; height: 600px; overflow: hidden; }}
        .mermaid {{ width: 100%; height: 100%; }}
        .mermaid svg {{ width: 100%; height: 100%; }}
        .zoom-controls {{ position: absolute; top: 10px; right: 10px; display: flex; flex-direction: column; gap: 5px; z-index: 100; }}
        .zoom-btn {{ width: 36px; height: 36px; border: none; background: white; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); cursor: pointer; font-size: 18px; font-weight: bold; color: #333; }}
        .zoom-btn:hover {{ background: #f0f0f0; }}
        .zoom-info {{ position: absolute; bottom: 10px; left: 10px; background: rgba(255,255,255,0.9); padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #666; }}
        .node-list {{ max-height: 400px; overflow-y: auto; }}
        .node-item {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .node-item:last-child {{ border-bottom: none; }}
        .node-title {{ font-weight: 500; color: #333; }}
        .node-meta {{ font-size: 12px; color: #888; margin-top: 3px; }}
        .node-type {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 500; }}
        .type-document {{ background: #e1f5fe; color: #01579b; }}
        .type-requirement {{ background: #fff3e0; color: #e65100; }}
        .type-checkbox {{ background: #e8f5e9; color: #2e7d32; }}
        .type-signature {{ background: #ffebee; color: #c62828; }}
        .type-field {{ background: #f3e5f5; color: #7b1fa2; }}
        .type-condition {{ background: #fffde7; color: #f57f17; }}
        .type-attachment {{ background: #e0f2f1; color: #00695c; }}
        .type-deadline {{ background: #fce4ec; color: #ad1457; }}
        .edge-type {{ background: #eceff1; color: #546e7a; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
        .status-completed {{ color: #2e7d32; }}
        .status-not_started {{ color: #f57c00; }}
        .tabs {{ display: flex; gap: 5px; margin-bottom: 15px; flex-wrap: wrap; }}
        .tab {{ padding: 8px 16px; border: none; background: #e0e0e0; cursor: pointer; border-radius: 4px; }}
        .tab.active {{ background: #1976d2; color: white; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #fafafa; font-weight: 600; }}
        .legend {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
        .legend-section {{ padding: 15px; background: #fafafa; border-radius: 8px; }}
        .legend-item {{ display: flex; align-items: center; gap: 10px; margin: 8px 0; font-size: 14px; }}
        .legend-icon {{ width: 24px; height: 24px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Tender Requirements Analysis</h1>

        <div class="stats">
            <div class="stat-card">
                <h3>Total Requirements</h3>
                <div class="value">{stats['total_nodes']}</div>
                <div class="detail">across {len(by_document)} documents</div>
            </div>
            <div class="stat-card">
                <h3>Relationships</h3>
                <div class="value">{len(graph.edges)}</div>
                <div class="detail">dependencies between items</div>
            </div>
            <div class="stat-card">
                <h3>Completion</h3>
                <div class="value">{stats['completion_percentage']}%</div>
                <div class="progress-bar"><div class="progress-fill" style="width: {stats['completion_percentage']}%"></div></div>
            </div>
            <div class="stat-card">
                <h3>Critical Items</h3>
                <div class="value">{len([n for n in graph.nodes.values() if 'ausschluss' in (n.title + n.description).lower() or 'zwingend' in (n.title + n.description).lower()])}</div>
                <div class="detail">may cause disqualification</div>
            </div>
        </div>

        <div class="section">
            <h2>Legend</h2>
            <div class="legend">
                <div class="legend-section">
                    <h3>Node Types (What was extracted)</h3>
                    <div class="legend-item"><div class="legend-icon" style="background:#e1f5fe;color:#01579b">D</div> <strong>Document</strong> - Physical document to submit</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#fff3e0;color:#e65100">R</div> <strong>Requirement</strong> - Something that must be done/provided</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#f3e5f5;color:#7b1fa2">F</div> <strong>Field</strong> - Form field to fill in</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#e8f5e9;color:#2e7d32">C</div> <strong>Checkbox</strong> - Checkbox to check/uncheck</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#ffebee;color:#c62828">S</div> <strong>Signature</strong> - Where signature is required</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#fffde7;color:#f57f17">C</div> <strong>Condition</strong> - Conditional clause (if X then Y)</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#fce4ec;color:#ad1457">D</div> <strong>Deadline</strong> - Time-based requirement</div>
                    <div class="legend-item"><div class="legend-icon" style="background:#e0f2f1;color:#00695c">A</div> <strong>Attachment</strong> - File/document to attach</div>
                </div>
                <div class="legend-section">
                    <h3>Edge Types (Relationships)</h3>
                    <div class="legend-item"><span class="edge-type">requires</span> A needs B to be complete</div>
                    <div class="legend-item"><span class="edge-type">conditional_on</span> A only applies if B is true</div>
                    <div class="legend-item"><span class="edge-type">part_of</span> A is part of B</div>
                    <div class="legend-item"><span class="edge-type">references</span> A references B</div>
                    <h3 style="margin-top:15px">Graph Structure</h3>
                    <div class="legend-item">📄 <strong>Blue boxes</strong> = Source documents</div>
                    <div class="legend-item">📝 Items inside = Extracted requirements</div>
                    <div class="legend-item">➡️ Dashed arrows = Dependencies</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Requirements by Type</h2>
            <table>
                <tr><th>Type</th><th>Count</th><th>Completed</th></tr>
                {"".join(type_stats_html)}
            </table>
        </div>

        <div class="section">
            <h2>Graph Visualization</h2>
            <p style="color:#666;margin-bottom:15px;">Each colored box represents an extracted item (colors match legend). Dashed arrows show dependencies. Use controls or mouse wheel to zoom.</p>
            <div class="graph-container">
                <div class="zoom-controls">
                    <button class="zoom-btn" onclick="zoomIn()" title="Zoom In">+</button>
                    <button class="zoom-btn" onclick="zoomOut()" title="Zoom Out">-</button>
                    <button class="zoom-btn" onclick="resetZoom()" title="Reset">R</button>
                    <button class="zoom-btn" onclick="fitGraph()" title="Fit to View">F</button>
                </div>
                <div class="graph-wrapper">
                    <div class="mermaid" id="mermaid-graph">
{mermaid_code}
                    </div>
                </div>
                <div class="zoom-info">Scroll to zoom | Drag to pan | R=Reset | F=Fit</div>
            </div>
        </div>

        <div class="section">
            <h2>Relationships ({len(graph.edges)} edges)</h2>
            {"<p style='color:#888'>No relationships extracted yet.</p>" if not edges_html else f'''
            <table>
                <tr><th>From</th><th>Relationship</th><th>To</th></tr>
                {"".join(edges_html)}
            </table>
            '''}
        </div>

        <div class="section">
            <h2>All Requirements</h2>
            <div class="tabs">
                {"".join(tabs_html)}
            </div>
            {"".join(content_html)}
        </div>

        <div class="section">
            <h2>By Source Document</h2>
            <table>
                <tr><th>Document</th><th>Items</th><th>Breakdown</th></tr>
                {"".join(docs_html)}
            </table>
        </div>
    </div>

    <script>
        let panZoomInstance = null;

        mermaid.initialize({{
            startOnLoad: false,
            theme: 'default',
            maxTextSize: 500000,
            flowchart: {{
                useMaxWidth: false,
                htmlLabels: true,
                curve: 'basis'
            }},
            securityLevel: 'loose'
        }});

        // Render mermaid and then init pan-zoom
        document.addEventListener('DOMContentLoaded', async function() {{
            const element = document.getElementById('mermaid-graph');
            const graphDefinition = element.textContent;

            try {{
                const {{ svg }} = await mermaid.render('mermaid-svg', graphDefinition);
                element.innerHTML = svg;

                // Initialize svg-pan-zoom after a short delay
                setTimeout(() => {{
                    const svgElement = element.querySelector('svg');
                    if (svgElement) {{
                        // Make SVG fill the container
                        svgElement.style.width = '100%';
                        svgElement.style.height = '100%';
                        svgElement.setAttribute('preserveAspectRatio', 'xMidYMid meet');

                        panZoomInstance = svgPanZoom(svgElement, {{
                            zoomEnabled: true,
                            controlIconsEnabled: false,
                            fit: true,
                            center: true,
                            minZoom: 0.1,
                            maxZoom: 10,
                            zoomScaleSensitivity: 0.3
                        }});
                    }}
                }}, 100);
            }} catch (e) {{
                console.error('Mermaid render error:', e);
                element.innerHTML = '<p style="color:red">Error rendering graph. Graph may be too large.</p>';
            }}
        }});

        function zoomIn() {{
            if (panZoomInstance) panZoomInstance.zoomIn();
        }}

        function zoomOut() {{
            if (panZoomInstance) panZoomInstance.zoomOut();
        }}

        function resetZoom() {{
            if (panZoomInstance) {{
                panZoomInstance.reset();
            }}
        }}

        function fitGraph() {{
            if (panZoomInstance) {{
                panZoomInstance.fit();
                panZoomInstance.center();
            }}
        }}

        function showTab(type) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + type).classList.add('active');
        }}
    </script>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def print_graph_summary(graph: RequirementGraph):
    """Print a text summary of the graph."""
    print("\n" + "="*70)
    print("REQUIREMENT GRAPH SUMMARY")
    print("="*70)

    # By type
    by_type = defaultdict(list)
    for node in graph.nodes.values():
        by_type[node.type].append(node)

    print("\n📊 NODES (What was extracted):")
    print("-" * 50)
    for node_type in NodeType:
        nodes = by_type.get(node_type, [])
        if nodes:
            completed = len([n for n in nodes if n.status == CompletionStatus.COMPLETED])
            print(f"  {node_type.value:15} : {len(nodes):4} items ({completed} completed)")

    # By source document
    by_doc = defaultdict(list)
    for node in graph.nodes.values():
        if node.source_document:
            by_doc[Path(node.source_document).name].append(node)

    print(f"\n📄 SOURCE DOCUMENTS ({len(by_doc)} files):")
    print("-" * 50)
    for doc, nodes in sorted(by_doc.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"  {doc[:45]:45} : {len(nodes):3} items")
    if len(by_doc) > 15:
        print(f"  ... and {len(by_doc) - 15} more documents")

    # Edges
    print(f"\n🔗 EDGES (Relationships): {len(graph.edges)}")
    print("-" * 50)
    if graph.edges:
        by_edge_type = defaultdict(int)
        for edge in graph.edges.values():
            by_edge_type[edge.type] += 1
        for edge_type, count in sorted(by_edge_type.items(), key=lambda x: -x[1]):
            print(f"  {edge_type.value:20} : {count}")

        print("\n  Sample relationships:")
        for i, edge in enumerate(list(graph.edges.values())[:5]):
            source = graph.get_node(edge.source_id)
            target = graph.get_node(edge.target_id)
            if source and target:
                print(f"    • {source.title[:30]} --[{edge.type.value}]--> {target.title[:30]}")
    else:
        print("  No relationships extracted")

    # Completion
    stats = graph.get_completion_stats()
    print(f"\n✅ COMPLETION: {stats['completion_percentage']}%")
    print(f"   {stats['completed_items']} of {stats['applicable_items']} applicable items done")

    print("\n" + "="*70)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Visualize tender requirement graph")
    parser.add_argument("directory", help="Tender directory with .tender_state")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--mermaid", action="store_true", help="Output Mermaid diagram")
    parser.add_argument("--summary", action="store_true", help="Print text summary")
    parser.add_argument("--open", action="store_true", help="Open HTML in browser")

    args = parser.parse_args()

    # Load graph
    graph_path = Path(args.directory) / ".tender_state" / "requirement_graph.json"
    if not graph_path.exists():
        print(f"Error: No graph found at {graph_path}")
        print("Run 'python tender_manager.py <directory> --process' first")
        sys.exit(1)

    graph = RequirementGraph.load(str(graph_path))
    print(f"Loaded graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")

    if args.summary or (not args.html and not args.mermaid):
        print_graph_summary(graph)

    if args.mermaid:
        print("\n" + generate_mermaid(graph))

    if args.html:
        output_path = Path(args.directory) / ".tender_state" / "graph_report.html"
        generate_html_report(graph, str(output_path))
        print(f"\nHTML report saved to: {output_path}")

        if args.open:
            import webbrowser
            webbrowser.open(f"file://{output_path.absolute()}")


if __name__ == "__main__":
    main()
