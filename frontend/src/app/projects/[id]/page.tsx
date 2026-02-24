"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type ProjectDetail, type Document, type TodoResponse } from "@/lib/api";
import { createClient } from "@/lib/supabase";
import DocumentUploader from "@/components/DocumentUploader";
import ProcessingProgress from "@/components/ProcessingProgress";
import TodoList from "@/components/TodoList";
import GraphVisualization from "@/components/GraphVisualization";

type Tab = "overview" | "documents" | "todos" | "graph";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [todos, setTodos] = useState<TodoResponse | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string>("");

  const loadProject = useCallback(async (t: string) => {
    const [proj, docs] = await Promise.all([
      api.projects.get(projectId, t),
      api.documents.list(projectId, t),
    ]);
    setProject(proj);
    setDocuments(docs);
  }, [projectId]);

  const loadTodos = useCallback(async (t: string) => {
    try {
      const data = await api.todos.list(projectId, t);
      setTodos(data);
    } catch (err) {
      console.error("Failed to load todos:", err);
    }
  }, [projectId]);

  useEffect(() => {
    async function init() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        setToken(session.access_token);
        await loadProject(session.access_token);
      }
      setLoading(false);
    }
    init();
  }, [loadProject]);

  // Load todos when tab is selected
  useEffect(() => {
    if (activeTab === "todos" && token && !todos) {
      loadTodos(token);
    }
  }, [activeTab, token, todos, loadTodos]);

  function handleDataChange() {
    if (token) {
      loadProject(token);
      setTodos(null); // Force reload on next visit
    }
  }

  function handleProcessingProgress() {
    if (token) {
      loadProject(token);
      // Refresh todos if they're currently visible
      if (todos) loadTodos(token);
    }
  }

  function handleProcessingComplete() {
    if (token) {
      loadProject(token);
      setTodos(null);
    }
  }

  function handleTodoUpdate() {
    if (token) {
      loadTodos(token);
      loadProject(token);
    }
  }

  if (loading) return <p className="text-text-secondary p-8">Loading...</p>;
  if (!project) return <p className="text-destructive p-8">Project not found</p>;

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "documents", label: `Documents (${documents.length})` },
    { key: "todos", label: "To-Do List" },
    { key: "graph", label: "Graph" },
  ];

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link href="/projects" className="text-sm text-text-secondary hover:text-foreground mb-2 inline-block">
          &larr; Back to Projects
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium text-foreground">{project.name}</h1>
            {project.tender_number && (
              <p className="text-sm text-text-secondary">#{project.tender_number}</p>
            )}
          </div>
          {project.deadline && (
            <div className="text-right">
              <p className="text-xs text-text-tertiary">Deadline</p>
              <p className="text-sm text-foreground">
                {new Date(project.deadline).toLocaleDateString("de-DE")}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="border border-border rounded-md p-4">
          <p className="text-xs text-text-secondary">Total Items</p>
          <p className="text-2xl font-medium text-foreground">{project.stats?.total_nodes || 0}</p>
        </div>
        <div className="border border-border rounded-md p-4">
          <p className="text-xs text-text-secondary">Completed</p>
          <p className="text-2xl font-medium text-success">{project.stats?.completed || 0}</p>
        </div>
        <div className="border border-border rounded-md p-4">
          <p className="text-xs text-text-secondary">Completion</p>
          <p className="text-2xl font-medium text-foreground">{project.stats?.completion_pct || 0}%</p>
        </div>
        <div className="border border-border rounded-md p-4">
          <p className="text-xs text-text-secondary">Documents</p>
          <p className="text-2xl font-medium text-foreground">{documents.length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border mb-6">
        <div className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 px-1 text-sm border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-foreground text-foreground font-medium"
                  : "border-transparent text-text-secondary hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="border-b border-border pb-6">
            <h3 className="font-medium text-foreground mb-2">Description</h3>
            <p className="text-text-secondary">{project.description || "No description"}</p>
          </div>
          {project.stats?.by_type && Object.keys(project.stats.by_type).length > 0 && (
            <div className="border-b border-border pb-6">
              <h3 className="font-medium text-foreground mb-4">Items by Type</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(project.stats.by_type).map(([type, count]) => (
                  <div key={type} className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${typeColor(type)}`} />
                    <span className="text-sm text-text-secondary capitalize">{type}</span>
                    <span className="text-sm font-medium text-foreground ml-auto">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Quick actions */}
          <div>
            <h3 className="font-medium text-foreground mb-3">AI Processing</h3>
            <ProcessingProgress
              projectId={projectId}
              token={token}
              documentCount={documents.length}
              onProgress={handleProcessingProgress}
              onComplete={handleProcessingComplete}
            />
          </div>
        </div>
      )}

      {activeTab === "documents" && (
        <div className="space-y-4">
          <DocumentUploader
            projectId={projectId}
            token={token}
            onUploadComplete={handleDataChange}
          />
          {/* Existing documents table */}
          {documents.length > 0 && (
            <div className="border border-border rounded-md overflow-hidden">
              <div className="px-5 py-3 border-b border-border">
                <h3 className="font-medium text-sm text-foreground">
                  Uploaded Documents ({documents.length})
                </h3>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-text-tertiary border-b border-border">
                    <th className="px-5 py-2 font-medium">Filename</th>
                    <th className="px-5 py-2 font-medium">Type</th>
                    <th className="px-5 py-2 font-medium">Size</th>
                    <th className="px-5 py-2 font-medium">Uploaded</th>
                    <th className="px-5 py-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-surface-hover transition-colors">
                      <td className="px-5 py-2.5 text-sm text-foreground">{doc.filename}</td>
                      <td className="px-5 py-2.5 text-sm text-text-secondary">{doc.file_type}</td>
                      <td className="px-5 py-2.5 text-sm text-text-secondary">{formatSize(doc.file_size)}</td>
                      <td className="px-5 py-2.5 text-sm text-text-secondary">
                        {new Date(doc.created_at).toLocaleDateString("de-DE")}
                      </td>
                      <td className="px-5 py-2.5">
                        <button
                          onClick={async () => {
                            await api.documents.delete(projectId, doc.id, token);
                            handleDataChange();
                          }}
                          className="text-xs text-destructive hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {/* Processing section below documents */}
          <div className="border-t border-border pt-5">
            <h3 className="font-medium text-sm text-foreground mb-3">AI Extraction</h3>
            <ProcessingProgress
              projectId={projectId}
              token={token}
              documentCount={documents.length}
              onProgress={handleProcessingProgress}
              onComplete={handleProcessingComplete}
            />
          </div>
        </div>
      )}

      {activeTab === "todos" && (
        <div>
          {!todos ? (
            <div className="text-center py-8 text-text-secondary">
              Loading to-do list...
            </div>
          ) : (
            <TodoList
              categories={todos.categories}
              projectId={projectId}
              token={token}
              onUpdate={handleTodoUpdate}
            />
          )}
        </div>
      )}

      {activeTab === "graph" && (
        <GraphVisualization projectId={projectId} token={token} />
      )}
    </div>
  );
}

function typeColor(type: string): string {
  const colors: Record<string, string> = {
    document: "bg-accent",
    requirement: "bg-priority-high",
    field: "bg-[#9065B0]",
    checkbox: "bg-success",
    signature: "bg-destructive",
    condition: "bg-warning",
    deadline: "bg-priority-critical",
    attachment: "bg-[#4DAB9A]",
  };
  return colors[type] || "bg-text-tertiary";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
