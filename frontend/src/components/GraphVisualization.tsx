"use client";

import { useState, useEffect, useRef } from "react";
import { Maximize2, Minimize2, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { api, type GraphData, type GraphNode, type GraphEdge } from "@/lib/api";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";

// @ts-expect-error — no types for cytoscape-fcose
import fcose from "cytoscape-fcose";

cytoscape.use(fcose);

interface GraphVisualizationProps {
  projectId: string;
  token: string;
}

const NODE_STYLES: Record<string, { bg: string; border: string; text: string }> = {
  document:   { bg: "#e1f5fe", border: "#01579b", text: "#01579b" },
  requirement:{ bg: "#fff3e0", border: "#e65100", text: "#e65100" },
  condition:  { bg: "#fffde7", border: "#f57f17", text: "#f57f17" },
  checkbox:   { bg: "#e8f5e9", border: "#2e7d32", text: "#2e7d32" },
  signature:  { bg: "#ffebee", border: "#c62828", text: "#c62828" },
  field:      { bg: "#f3e5f5", border: "#7b1fa2", text: "#7b1fa2" },
  attachment: { bg: "#e0f2f1", border: "#00695c", text: "#00695c" },
  deadline:   { bg: "#fce4ec", border: "#ad1457", text: "#ad1457" },
};

const STATUS_ICONS: Record<string, string> = {
  completed: " ✓",
  in_progress: " ◐",
  blocked: " ✗",
};

export default function GraphVisualization({ projectId, token }: GraphVisualizationProps) {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const cyContainerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    loadGraph();
  }, [projectId, token]);

  async function loadGraph() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.graph.get(projectId, token);
      setGraph(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  // Build and render Cytoscape when graph data is ready
  useEffect(() => {
    if (!graph || graph.nodes.length === 0 || !cyContainerRef.current) return;

    const elements = buildElements(graph.nodes, graph.edges);

    const cy = cytoscape({
      container: cyContainerRef.current,
      elements,
      style: [
        // Parent (document) nodes
        {
          selector: "node.doc-parent",
          style: {
            "background-color": "#f0f4f8",
            "border-color": "#01579b",
            "border-width": 2,
            "label": "data(label)",
            "text-valign": "top",
            "text-halign": "center",
            "font-size": 11,
            "font-weight": "bold",
            "color": "#01579b",
            "padding": "12px",
            "text-margin-y": 4,
            "shape": "roundrectangle",
          },
        },
        // Regular nodes — base style
        {
          selector: "node.item",
          style: {
            "label": "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": 9,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "width": "label",
            "height": "label",
            "padding": "8px",
            "shape": "roundrectangle",
            "border-width": 1.5,
            "background-color": "#fff3e0",
            "border-color": "#e65100",
            "color": "#37352F",
          },
        },
        // Per-type styles
        ...Object.entries(NODE_STYLES).map(([type, s]) => ({
          selector: `node.item.type-${type}`,
          style: {
            "background-color": s.bg,
            "border-color": s.border,
            "color": "#37352F",
          },
        })),
        // Completed nodes
        {
          selector: "node.status-completed",
          style: {
            "border-style": "double" as const,
            "border-width": 3,
            "opacity": 0.75,
          },
        },
        // Edges — z-compound-depth "top" ensures edges render above compound parent backgrounds
        {
          selector: "edge",
          style: {
            "width": 2.5,
            "line-color": "#546e7a",
            "target-arrow-color": "#546e7a",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 1,
            "opacity": 0.85,
            "label": "data(label)",
            "font-size": 8,
            "text-rotation": "autorotate",
            "text-margin-y": -8,
            "color": "#78909c",
            "z-compound-depth": "top",
          } as any,
        },
        {
          selector: "edge.conditional",
          style: {
            "line-style": "dashed",
            "line-color": "#f57f17",
            "target-arrow-color": "#f57f17",
            "color": "#f57f17",
          },
        },
        // Hover
        {
          selector: "node.item:active",
          style: {
            "overlay-opacity": 0.1,
          },
        },
      ],
      layout: { name: "preset" }, // will run layout after
      minZoom: 0.05,
      maxZoom: 5,
      wheelSensitivity: 0.3,
    });

    // Run fCoSE layout
    cy.layout({
      name: "fcose",
      animate: false,
      quality: "proof",
      randomize: true,
      nodeDimensionsIncludeLabels: true,
      packComponents: true,
      nodeRepulsion: 8000,
      idealEdgeLength: 80,
      edgeElasticity: 0.45,
      numIter: 2500,
      gravity: 0.25,
      gravityRange: 3.8,
      tilingPaddingVertical: 20,
      tilingPaddingHorizontal: 20,
    } as any).run();

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph]);

  function handleZoomIn() {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() * 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }

  function handleZoomOut() {
    const cy = cyRef.current;
    if (cy) cy.zoom({ level: cy.zoom() / 1.3, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  }

  function handleReset() {
    cyRef.current?.fit(undefined, 30);
  }

  function toggleFullscreen() {
    setIsFullscreen((prev) => !prev);
    setTimeout(() => {
      cyRef.current?.resize();
      cyRef.current?.fit(undefined, 30);
    }, 100);
  }

  if (loading) {
    return (
      <div className="border border-border rounded-md p-8 text-center text-text-secondary">
        Loading graph...
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-l-2 border-l-destructive bg-surface rounded-r-md p-6 text-center">
        <p className="text-sm text-foreground">{error}</p>
        <button onClick={loadGraph} className="mt-2 text-sm text-accent hover:underline">
          Retry
        </button>
      </div>
    );
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="border border-border rounded-md p-8 text-center text-text-secondary">
        No graph data yet. Upload documents and run AI extraction to see the requirement graph.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`${isFullscreen ? "fixed inset-0 z-50 bg-background" : "border border-border rounded-md"}`}
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-secondary">
            {graph.total_nodes} nodes, {graph.total_edges} edges
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={handleZoomIn} className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary transition-colors" title="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button onClick={handleZoomOut} className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary transition-colors" title="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </button>
          <button onClick={handleReset} className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary transition-colors" title="Reset view">
            <RotateCcw className="w-4 h-4" />
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <button onClick={toggleFullscreen} className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary transition-colors" title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}>
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Graph */}
      <div
        ref={cyContainerRef}
        className={`${isFullscreen ? "h-[calc(100vh-100px)]" : "h-[500px]"}`}
      />

      {/* Legend */}
      <div className="flex flex-wrap gap-3 px-4 py-2 border-t border-border">
        {Object.entries(NODE_STYLES).map(([type, s]) => (
          <div key={type} className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-sm border"
              style={{ backgroundColor: s.bg, borderColor: s.border }}
            />
            <span className="text-xs text-text-secondary capitalize">{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Build Cytoscape elements from graph data. Groups nodes by document when possible. */
function buildElements(nodes: GraphNode[], edges: GraphEdge[]): ElementDefinition[] {
  const elements: ElementDefinition[] = [];
  const docGroups = new Map<string, string>(); // document_id -> display name

  // Collect document parents
  for (const node of nodes) {
    if (node.document_id && node.documents?.filename && !docGroups.has(node.document_id)) {
      const name = node.documents.filename;
      const display = name.length > 40 ? name.slice(0, 37) + "..." : name;
      docGroups.set(node.document_id, display);
    }
  }

  // Add document parent nodes
  for (const [docId, label] of docGroups) {
    elements.push({
      data: { id: `doc-${docId}`, label },
      classes: "doc-parent",
    });
  }

  // Add item nodes
  for (const node of nodes) {
    const typeKey = node.type.toLowerCase();
    const statusIcon = STATUS_ICONS[node.status] || "";
    const label = truncate(node.title, 40) + statusIcon;

    const data: Record<string, unknown> = {
      id: node.id,
      label,
      nodeType: typeKey,
    };

    // Set parent for compound grouping
    if (node.document_id && docGroups.has(node.document_id)) {
      data.parent = `doc-${node.document_id}`;
    }

    const classes = ["item", `type-${typeKey}`];
    if (node.status === "completed") classes.push("status-completed");

    elements.push({ data, classes: classes.join(" ") });
  }

  // Add edges
  const nodeIds = new Set(nodes.map((n) => n.id));
  for (const edge of edges) {
    if (!nodeIds.has(edge.source_node_id) || !nodeIds.has(edge.target_node_id)) continue;

    const edgeType = edge.type.toLowerCase();
    const classes = edgeType === "conditional_on" || edgeType === "references" ? "conditional" : "";

    elements.push({
      data: {
        id: edge.id,
        source: edge.source_node_id,
        target: edge.target_node_id,
        edgeType: edge.type,
        label: edge.type.replace(/_/g, " "),
      },
      classes,
    });
  }

  return elements;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + "\u2026";
}
