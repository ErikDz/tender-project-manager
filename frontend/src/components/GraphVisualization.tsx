"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import { Maximize2, Minimize2 } from "lucide-react";
import { api, type GraphData, type GraphNode, type GraphEdge } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const NODE_STYLES: Record<string, { bg: string; border: string; badge: string }> = {
  document:    { bg: "#e1f5fe", border: "#01579b", badge: "#01579b" },
  requirement: { bg: "#fff3e0", border: "#e65100", badge: "#e65100" },
  condition:   { bg: "#fffde7", border: "#f57f17", badge: "#f57f17" },
  checkbox:    { bg: "#e8f5e9", border: "#2e7d32", badge: "#2e7d32" },
  signature:   { bg: "#ffebee", border: "#c62828", badge: "#c62828" },
  field:       { bg: "#f3e5f5", border: "#7b1fa2", badge: "#7b1fa2" },
  attachment:  { bg: "#e0f2f1", border: "#00695c", badge: "#00695c" },
  deadline:    { bg: "#fce4ec", border: "#ad1457", badge: "#ad1457" },
};

const EDGE_COLORS: Record<string, string> = {
  requires: "#546e7a",
  required_by: "#546e7a",
  conditional_on: "#f57f17",
  triggers: "#2e7d32",
  part_of: "#01579b",
  references: "#78909c",
  mutually_exclusive: "#c62828",
  depends_on: "#7b1fa2",
};

const NODE_WIDTH = 200;
const NODE_HEIGHT = 60;
const GROUP_PADDING = 40;

/* ------------------------------------------------------------------ */
/*  Custom Node Components                                             */
/* ------------------------------------------------------------------ */

type ItemNodeData = {
  label: string;
  nodeType: string;
  status: string;
  description: string;
  onToggleStatus: (nodeId: string, currentStatus: string) => void;
};

function RequirementNode({ id, data }: NodeProps<Node<ItemNodeData>>) {
  const typeKey = data.nodeType;
  const style = NODE_STYLES[typeKey] || NODE_STYLES.requirement;
  const isCompleted = data.status === "completed";

  return (
    <div
      style={{
        background: style.bg,
        border: `2px solid ${style.border}`,
        borderRadius: 6,
        padding: "6px 10px",
        minWidth: 160,
        maxWidth: 220,
        opacity: isCompleted ? 0.7 : 1,
        cursor: "default",
      }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0, width: 1, height: 1 }} />

      <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
        {/* Checkbox */}
        <button
          className="nopan nodrag"
          onClick={(e) => {
            e.stopPropagation();
            data.onToggleStatus(id, data.status);
          }}
          style={{
            width: 16,
            height: 16,
            minWidth: 16,
            marginTop: 2,
            borderRadius: 3,
            border: `1.5px solid ${style.border}`,
            background: isCompleted ? style.border : "white",
            color: "white",
            fontSize: 10,
            lineHeight: "14px",
            textAlign: "center",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {isCompleted ? "✓" : ""}
        </button>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Type badge */}
          <span
            style={{
              fontSize: 8,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              color: style.badge,
              display: "block",
              marginBottom: 2,
            }}
          >
            {typeKey}
          </span>
          {/* Title */}
          <div
            style={{
              fontSize: 11,
              color: "#37352f",
              lineHeight: "14px",
              textDecoration: isCompleted ? "line-through" : "none",
              wordBreak: "break-word",
            }}
            title={data.description || data.label}
          >
            {data.label}
          </div>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, width: 1, height: 1 }} />
    </div>
  );
}

function DocumentGroupNode({ data }: NodeProps) {
  return (
    <div
      style={{
        background: "rgba(225, 245, 254, 0.5)",
        border: "2px solid #01579b",
        borderRadius: 8,
        padding: 12,
        width: "100%",
        height: "100%",
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: "#01579b",
          marginBottom: 4,
        }}
      >
        {(data as { label: string }).label}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Node types (defined outside component to prevent re-registration)  */
/* ------------------------------------------------------------------ */

const nodeTypes = {
  requirement: RequirementNode,
  documentGroup: DocumentGroupNode,
};

/* ------------------------------------------------------------------ */
/*  Layout with dagre                                                  */
/* ------------------------------------------------------------------ */

function layoutElements(
  nodes: Node[],
  edges: Edge[],
): { nodes: Node[]; edges: Edge[] } {
  // Separate group parents and children
  const groups = nodes.filter((n) => n.type === "documentGroup");
  const items = nodes.filter((n) => n.type !== "documentGroup");

  // Group items by parentId
  const childrenByParent = new Map<string, Node[]>();
  const orphans: Node[] = [];
  for (const item of items) {
    const pid = item.parentId;
    if (pid) {
      const list = childrenByParent.get(pid) || [];
      list.push(item);
      childrenByParent.set(pid, list);
    } else {
      orphans.push(item);
    }
  }

  // Layout children within each group using dagre
  const positionedItems: Node[] = [];
  const groupSizes = new Map<string, { w: number; h: number; count: number }>();

  for (const group of groups) {
    const children = childrenByParent.get(group.id) || [];
    if (children.length === 0) {
      groupSizes.set(group.id, { w: NODE_WIDTH + GROUP_PADDING * 2, h: NODE_HEIGHT + GROUP_PADDING + 30, count: 0 });
      continue;
    }

    // Build a sub-graph for children of this group
    const childIds = new Set(children.map((c) => c.id));
    const childEdges = edges.filter(
      (e) => childIds.has(e.source) && childIds.has(e.target),
    );

    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "TB", nodesep: 30, ranksep: 40, marginx: 10, marginy: 10 });
    g.setDefaultEdgeLabel(() => ({}));

    for (const c of children) {
      g.setNode(c.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    }
    for (const e of childEdges) {
      g.setEdge(e.source, e.target);
    }

    dagre.layout(g);

    let maxX = 0;
    let maxY = 0;
    for (const c of children) {
      const pos = g.node(c.id);
      const x = pos.x - NODE_WIDTH / 2;
      const y = pos.y - NODE_HEIGHT / 2;
      maxX = Math.max(maxX, pos.x + NODE_WIDTH / 2);
      maxY = Math.max(maxY, pos.y + NODE_HEIGHT / 2);
      positionedItems.push({
        ...c,
        position: { x: x + GROUP_PADDING, y: y + GROUP_PADDING + 20 }, // offset for label
      });
    }

    groupSizes.set(group.id, {
      w: maxX + GROUP_PADDING * 2,
      h: maxY + GROUP_PADDING + 30,
      count: children.length,
    });
  }

  // Layout orphans
  for (let i = 0; i < orphans.length; i++) {
    positionedItems.push({
      ...orphans[i],
      position: { x: (i % 5) * (NODE_WIDTH + 30), y: Math.floor(i / 5) * (NODE_HEIGHT + 30) },
    });
  }

  // Layout groups in a compact grid (centered, wrapping into rows)
  const GAP = 60;
  const sortedGroups = [...groups].sort((a, b) => {
    const sa = groupSizes.get(a.id)!;
    const sb = groupSizes.get(b.id)!;
    return sb.count - sa.count; // largest groups first
  });

  // Determine columns: aim for roughly square overall layout
  const cols = Math.max(1, Math.min(sortedGroups.length, Math.ceil(Math.sqrt(sortedGroups.length))));

  // Arrange into rows
  const rows: typeof sortedGroups[] = [];
  for (let i = 0; i < sortedGroups.length; i += cols) {
    rows.push(sortedGroups.slice(i, i + cols));
  }

  const positionedGroups: Node[] = [];
  let cursorY = 0;

  for (const row of rows) {
    const rowHeight = Math.max(...row.map((g) => groupSizes.get(g.id)!.h));
    let cursorX = 0;

    for (const group of row) {
      const size = groupSizes.get(group.id)!;
      positionedGroups.push({
        ...group,
        position: { x: cursorX, y: cursorY },
        style: { width: size.w, height: size.h },
      });
      cursorX += size.w + GAP;
    }

    cursorY += rowHeight + GAP;
  }

  // Parents must come before children in the array
  return {
    nodes: [...positionedGroups, ...positionedItems],
    edges,
  };
}

/* ------------------------------------------------------------------ */
/*  Convert API data → React Flow elements                             */
/* ------------------------------------------------------------------ */

function buildElements(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
  onToggleStatus: (nodeId: string, currentStatus: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const docGroups = new Map<string, string>();

  // Collect document groups
  for (const n of graphNodes) {
    if (n.document_id && n.documents?.filename && !docGroups.has(n.document_id)) {
      const name = n.documents.filename;
      docGroups.set(n.document_id, name.length > 50 ? name.slice(0, 47) + "..." : name);
    }
  }

  // Add group nodes
  for (const [docId, label] of docGroups) {
    nodes.push({
      id: `doc-${docId}`,
      type: "documentGroup",
      position: { x: 0, y: 0 },
      data: { label },
    });
  }

  // Add item nodes
  for (const n of graphNodes) {
    const typeKey = n.type.toLowerCase();
    const node: Node<ItemNodeData> = {
      id: n.id,
      type: "requirement",
      position: { x: 0, y: 0 },
      data: {
        label: n.title.length > 50 ? n.title.slice(0, 47) + "\u2026" : n.title,
        nodeType: typeKey,
        status: n.status,
        description: n.description || "",
        onToggleStatus,
      },
    };

    if (n.document_id && docGroups.has(n.document_id)) {
      node.parentId = `doc-${n.document_id}`;
      node.extent = "parent";
    }

    nodes.push(node);
  }

  // Add edges
  const nodeIds = new Set(graphNodes.map((n) => n.id));
  const edges: Edge[] = [];
  for (const e of graphEdges) {
    if (!nodeIds.has(e.source_node_id) || !nodeIds.has(e.target_node_id)) continue;

    const edgeType = e.type.toLowerCase();
    const color = EDGE_COLORS[edgeType] || "#546e7a";
    const isDashed = edgeType === "conditional_on" || edgeType === "references";

    edges.push({
      id: e.id,
      source: e.source_node_id,
      target: e.target_node_id,
      label: e.type.replace(/_/g, " "),
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: {
        stroke: color,
        strokeWidth: 2,
        strokeDasharray: isDashed ? "6 3" : undefined,
      },
      labelStyle: { fontSize: 9, fill: color, fontWeight: 500 },
      labelBgStyle: { fill: "white", fillOpacity: 0.85 },
      labelBgPadding: [4, 2] as [number, number],
      zIndex: 1,
    });
  }

  return layoutElements(nodes, edges);
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

interface GraphVisualizationProps {
  projectId: string;
  token: string;
  onUpdate?: () => void;
}

export default function GraphVisualization({ projectId, token, onUpdate }: GraphVisualizationProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  async function loadGraph() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.graph.get(projectId, token);
      setGraphData(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGraph();
  }, [projectId, token]);

  // Use a ref so the toggle callback baked into nodes never goes stale
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const handleToggleStatus = useCallback(
    async (nodeId: string, currentStatus: string) => {
      const newStatus = currentStatus === "completed" ? "not_started" : "completed";
      try {
        await api.graph.updateNode(projectId, nodeId, { status: newStatus }, token);
        // Update local node state — this is the only place we mutate nodes after initial build
        setNodes((prev) =>
          prev.map((n) =>
            n.id === nodeId
              ? { ...n, data: { ...n.data, status: newStatus } }
              : n,
          ),
        );
        onUpdateRef.current?.();
      } catch (err) {
        console.error("Failed to update node status:", err);
      }
    },
    // Stable deps only — no onUpdate (use ref instead)
    [projectId, token, setNodes],
  );

  // Build React Flow elements only when graph data changes (not when callback ref changes)
  useEffect(() => {
    if (!graphData || graphData.nodes.length === 0) return;
    const { nodes: n, edges: e } = buildElements(graphData.nodes, graphData.edges, handleToggleStatus);
    setNodes(n);
    setEdges(e);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData, setNodes, setEdges]);

  const defaultEdgeOptions = useMemo(() => ({ zIndex: 1 }), []);

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

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="border border-border rounded-md p-8 text-center text-text-secondary">
        No graph data yet. Upload documents and run AI extraction to see the requirement graph.
      </div>
    );
  }

  return (
    <div className={`${isFullscreen ? "fixed inset-0 z-50 bg-background" : "border border-border rounded-md"}`}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <span className="text-sm text-text-secondary">
          {graphData.total_nodes} nodes, {graphData.total_edges} edges
          <span className="ml-3 text-xs text-text-tertiary">Click checkbox to toggle completion</span>
        </span>
        <button
          onClick={() => {
            setIsFullscreen((p) => !p);
          }}
          className="p-1.5 rounded-md hover:bg-surface-hover text-text-secondary transition-colors"
          title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* Graph canvas */}
      <div className={`${isFullscreen ? "h-[calc(100vh-100px)]" : "h-[500px]"}`}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.05}
          maxZoom={3}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} color="#e5e5e5" />
          <Controls showInteractive={false} />
          <MiniMap
            nodeStrokeWidth={3}
            pannable
            zoomable
            style={{ width: 150, height: 100 }}
          />
        </ReactFlow>
      </div>

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
