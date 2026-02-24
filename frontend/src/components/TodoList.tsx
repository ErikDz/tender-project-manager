"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, AlertTriangle } from "lucide-react";
import { api, type TodoCategory, type TodoItem } from "@/lib/api";

interface TodoListProps {
  categories: TodoCategory[];
  projectId: string;
  token: string;
  onUpdate: () => void;
}

const PRIORITY_DOTS: Record<string, string> = {
  CRITICAL: "bg-priority-critical",
  HIGH: "bg-priority-high",
  MEDIUM: "bg-priority-medium",
  LOW: "bg-priority-low",
};

const STATUS_COLORS: Record<string, string> = {
  not_started: "border-text-tertiary",
  in_progress: "border-accent bg-accent-light",
  completed: "border-success bg-success",
  not_applicable: "border-surface-active bg-surface-active",
  blocked: "border-destructive bg-[#FBE9E9]",
};

/** Group items by source_document, preserving order. Items without a document go last under "". */
function groupByDocument(items: TodoItem[]): [string, TodoItem[]][] {
  const groups = new Map<string, TodoItem[]>();
  for (const item of items) {
    const key = item.source_document || "";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  // Put items with a document first, ungrouped last
  const sorted: [string, TodoItem[]][] = [];
  for (const [key, vals] of groups) {
    if (key) sorted.push([key, vals]);
  }
  const ungrouped = groups.get("");
  if (ungrouped) sorted.push(["", ungrouped]);
  return sorted;
}

export default function TodoList({ categories, projectId, token, onUpdate }: TodoListProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [updating, setUpdating] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  async function toggleStatus(item: TodoItem) {
    setUpdating(item.id);
    try {
      const newStatus = item.status === "completed" ? "not_started" : "completed";
      await api.todos.setStatus(projectId, item.id, newStatus, token);
      onUpdate();
    } catch (err) {
      console.error("Failed to update:", err);
    } finally {
      setUpdating(null);
    }
  }

  function toggleCollapse(name: string) {
    setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }));
  }

  // Filter items
  const filteredCategories = categories
    .map((cat) => ({
      ...cat,
      items: cat.items.filter((item) => {
        if (filter === "all") return true;
        if (filter === "pending") return item.status !== "completed";
        if (filter === "critical") return item.priority === "CRITICAL";
        return true;
      }),
    }))
    .filter((cat) => cat.items.length > 0);

  const totalItems = categories.reduce((sum, c) => sum + c.items.length, 0);
  const completedItems = categories.reduce(
    (sum, c) => sum + c.items.filter((i) => i.status === "completed").length,
    0
  );

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-4">
          <span className="text-sm text-text-secondary">
            {completedItems}/{totalItems} completed
          </span>
          <div className="w-32 bg-surface-active rounded-full h-1">
            <div
              className="bg-foreground rounded-full h-1 transition-all"
              style={{
                width: `${totalItems > 0 ? (completedItems / totalItems) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
        <div className="flex gap-1">
          {["all", "pending", "critical"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-xs transition-colors ${
                filter === f
                  ? "text-foreground border-b-2 border-foreground"
                  : "text-text-tertiary hover:text-foreground"
              }`}
            >
              {f === "all" ? "All" : f === "pending" ? "Open" : "Critical"}
            </button>
          ))}
        </div>
      </div>

      {/* Category groups */}
      {filteredCategories.length === 0 ? (
        <div className="text-center py-8 text-text-secondary">
          {totalItems === 0
            ? "No requirements extracted yet. Upload documents and run AI extraction."
            : "No items match the current filter."}
        </div>
      ) : (
        filteredCategories.map((category) => {
          const isCollapsed = collapsed[category.name];
          const catCompleted = category.items.filter(
            (i) => i.status === "completed"
          ).length;

          return (
            <div key={category.name} className="border border-border rounded-md overflow-hidden">
              {/* Category header */}
              <button
                onClick={() => toggleCollapse(category.name)}
                className="w-full flex items-center justify-between px-5 py-3 hover:bg-surface-hover transition-colors border-b border-border"
              >
                <div className="flex items-center gap-2">
                  {isCollapsed ? (
                    <ChevronRight className="w-4 h-4 text-text-tertiary" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-text-tertiary" />
                  )}
                  <span className="font-medium text-sm text-foreground">
                    {category.name}
                  </span>
                  <span className="text-xs text-text-tertiary">
                    {catCompleted}/{category.items.length}
                  </span>
                </div>
                <div className="w-20 bg-surface-active rounded-full h-1">
                  <div
                    className="bg-foreground rounded-full h-1 transition-all"
                    style={{
                      width: `${
                        category.items.length > 0
                          ? (catCompleted / category.items.length) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </button>

              {/* Items grouped by source document */}
              {!isCollapsed && (
                <div className="divide-y divide-border">
                  {groupByDocument(category.items).map(([docName, items]) => (
                    <div key={docName}>
                      {/* Document sub-header */}
                      {docName && (
                        <div className="flex items-center gap-1.5 px-5 py-1.5 bg-surface">
                          <FileText className="w-3.5 h-3.5 text-text-tertiary" />
                          <span className="text-xs font-medium text-text-secondary">{docName}</span>
                          <span className="text-xs text-text-tertiary">
                            ({items.filter((i) => i.status === "completed").length}/{items.length})
                          </span>
                        </div>
                      )}
                      {items.map((item) => (
                        <div
                          key={item.id}
                          className={`flex items-start gap-3 px-5 py-3 hover:bg-surface-hover transition-colors ${
                            docName ? "pl-9" : ""
                          } ${item.status === "completed" ? "opacity-60" : ""}`}
                        >
                          {/* Checkbox */}
                          <button
                            onClick={() => toggleStatus(item)}
                            disabled={updating === item.id}
                            className={`mt-0.5 w-5 h-5 rounded border-2 shrink-0 flex items-center justify-center transition-colors ${
                              STATUS_COLORS[item.status] || STATUS_COLORS.not_started
                            } ${updating === item.id ? "animate-pulse" : ""}`}
                          >
                            {item.status === "completed" && (
                              <svg className="w-3 h-3 text-white" viewBox="0 0 12 12">
                                <path
                                  d="M3.5 6L5.5 8L8.5 4"
                                  stroke="currentColor"
                                  strokeWidth="2"
                                  fill="none"
                                  strokeLinecap="round"
                                />
                              </svg>
                            )}
                          </button>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <p
                              className={`text-sm leading-snug ${
                                item.status === "completed"
                                  ? "line-through text-text-tertiary"
                                  : "text-foreground"
                              }`}
                            >
                              {item.priority === "CRITICAL" && (
                                <AlertTriangle className="w-3.5 h-3.5 inline-block text-priority-critical mr-1 -mt-0.5" />
                              )}
                              {item.title}
                            </p>
                            {item.description && (
                              <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                                {item.description}
                              </p>
                            )}
                          </div>

                          {/* Priority indicator */}
                          <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary shrink-0">
                            <span className={`w-2 h-2 rounded-full ${PRIORITY_DOTS[item.priority] || PRIORITY_DOTS.MEDIUM}`} />
                            {item.priority.toLowerCase()}
                          </span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
