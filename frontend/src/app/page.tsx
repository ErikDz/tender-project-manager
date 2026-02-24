"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type Project } from "@/lib/api";
import { createClient } from "@/lib/supabase";
import {
  FolderOpen,
  AlertTriangle,
  Clock,
  CheckCircle,
  TrendingUp,
  Plus,
} from "lucide-react";

interface ProjectWithStats extends Project {
  stats?: {
    total_nodes: number;
    completed: number;
    completion_pct: number;
    by_type: Record<string, number>;
    critical_count?: number;
  };
}

export default function Dashboard() {
  const [projects, setProjects] = useState<ProjectWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function load() {
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) {
          setAuthenticated(false);
          setLoading(false);
          return;
        }
        const data = await api.projects.list(session.access_token);
        setProjects(data as ProjectWithStats[]);
      } catch (e) {
        console.error("Failed to load projects:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-text-tertiary">Loading dashboard...</div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <h1 className="text-2xl font-medium text-foreground">Tender Project Manager</h1>
        <p className="text-text-secondary">Sign in to manage your tender projects.</p>
        <Link
          href="/auth/login"
          className="bg-foreground text-white px-6 py-2 rounded-md hover:opacity-90 transition-opacity"
        >
          Sign In
        </Link>
      </div>
    );
  }

  // Compute summary statistics
  const totalProjects = projects.length;
  const activeProjects = projects.filter((p) => p.status === "active").length;
  const totalItems = projects.reduce((s, p) => s + (p.stats?.total_nodes || 0), 0);
  const completedItems = projects.reduce((s, p) => s + (p.stats?.completed || 0), 0);
  const avgCompletion =
    totalProjects > 0
      ? Math.round(
          projects.reduce((s, p) => s + (p.stats?.completion_pct || 0), 0) / totalProjects
        )
      : 0;

  // Find projects with upcoming deadlines (next 14 days)
  const now = new Date();
  const twoWeeks = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000);
  const upcomingDeadlines = projects
    .filter((p) => p.deadline && new Date(p.deadline) <= twoWeeks && new Date(p.deadline) >= now)
    .sort((a, b) => new Date(a.deadline!).getTime() - new Date(b.deadline!).getTime());

  // Overdue projects
  const overdueProjects = projects.filter(
    (p) => p.deadline && new Date(p.deadline) < now && (p.stats?.completion_pct || 0) < 100
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-medium text-foreground">Dashboard</h1>
        <Link
          href="/projects/new"
          className="flex items-center gap-2 text-sm text-accent hover:underline"
        >
          <Plus className="w-4 h-4" />
          New Project
        </Link>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="border border-border rounded-md p-5">
          <p className="text-xs text-text-secondary mb-1">Projects</p>
          <p className="text-2xl font-medium text-foreground">{totalProjects}</p>
        </div>
        <div className="border border-border rounded-md p-5">
          <p className="text-xs text-text-secondary mb-1">Completed Items</p>
          <p className="text-2xl font-medium text-foreground">
            {completedItems}
            <span className="text-sm font-normal text-text-tertiary">/{totalItems}</span>
          </p>
        </div>
        <div className="border border-border rounded-md p-5">
          <p className="text-xs text-text-secondary mb-1">Avg. Completion</p>
          <p className="text-2xl font-medium text-foreground">{avgCompletion}%</p>
        </div>
        <div className="border border-border rounded-md p-5">
          <p className="text-xs text-text-secondary mb-1">
            {overdueProjects.length > 0 ? "Overdue" : "Upcoming Deadlines"}
          </p>
          <p className={`text-2xl font-medium ${overdueProjects.length > 0 ? "text-destructive" : "text-warning"}`}>
            {overdueProjects.length > 0 ? overdueProjects.length : upcomingDeadlines.length}
          </p>
        </div>
      </div>

      {/* Alerts */}
      {overdueProjects.length > 0 && (
        <div className="border-l-2 border-l-destructive bg-surface rounded-r-md px-4 py-3 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-destructive" />
            <span className="text-sm font-medium text-foreground">Overdue Projects</span>
          </div>
          <div className="space-y-1">
            {overdueProjects.map((p) => (
              <Link
                key={p.id}
                href={`/projects/${p.id}`}
                className="flex items-center justify-between text-sm text-text-secondary hover:text-foreground py-1"
              >
                <span>{p.name}</span>
                <span className="text-xs">
                  Due {new Date(p.deadline!).toLocaleDateString("de-DE")} ({p.stats?.completion_pct || 0}% done)
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {upcomingDeadlines.length > 0 && (
        <div className="border-l-2 border-l-warning bg-surface rounded-r-md px-4 py-3 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-warning" />
            <span className="text-sm font-medium text-foreground">Upcoming Deadlines</span>
          </div>
          <div className="space-y-1">
            {upcomingDeadlines.map((p) => {
              const daysLeft = Math.ceil(
                (new Date(p.deadline!).getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
              );
              return (
                <Link
                  key={p.id}
                  href={`/projects/${p.id}`}
                  className="flex items-center justify-between text-sm text-text-secondary hover:text-foreground py-1"
                >
                  <span>{p.name}</span>
                  <span className="text-xs">
                    {daysLeft} day{daysLeft !== 1 ? "s" : ""} left ({p.stats?.completion_pct || 0}%
                    done)
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Project Cards */}
      {projects.length === 0 ? (
        <div className="text-center py-16 border border-border rounded-md">
          <FolderOpen className="w-12 h-12 text-text-tertiary mx-auto mb-4" />
          <p className="text-text-secondary mb-4">No projects yet</p>
          <Link
            href="/projects/new"
            className="inline-flex items-center gap-2 text-sm text-accent hover:underline"
          >
            <Plus className="w-4 h-4" />
            Create your first project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => {
            const pct = project.stats?.completion_pct || 0;
            return (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="border border-border rounded-md p-5 hover:bg-surface-hover transition-colors group"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-foreground">
                    {project.name}
                  </h3>
                  <span className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
                    <span className={`w-2 h-2 rounded-full ${
                      project.status === "active" ? "bg-success" : "bg-text-tertiary"
                    }`} />
                    {project.status}
                  </span>
                </div>

                {project.tender_number && (
                  <p className="text-xs text-text-tertiary mb-1">#{project.tender_number}</p>
                )}

                {project.description && (
                  <p className="text-sm text-text-secondary mb-3 line-clamp-2">{project.description}</p>
                )}

                {/* Completion bar */}
                <div className="mt-auto pt-3">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-text-secondary">
                      {project.stats?.completed || 0}/{project.stats?.total_nodes || 0} items
                    </span>
                    <span className="text-text-secondary">{pct}%</span>
                  </div>
                  <div className="w-full bg-surface-active rounded-full h-1">
                    <div
                      className="bg-foreground rounded-full h-1 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>

                {project.deadline && (
                  <div className="flex items-center gap-1 mt-3">
                    <Clock className="w-3 h-3 text-text-tertiary" />
                    <span className="text-xs text-text-secondary">
                      {new Date(project.deadline).toLocaleDateString("de-DE")}
                    </span>
                  </div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
