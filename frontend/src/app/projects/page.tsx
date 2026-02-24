"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type Project } from "@/lib/api";
import { createClient } from "@/lib/supabase";

const STATUS_DOTS: Record<string, string> = {
  active: "bg-success",
  submitted: "bg-accent",
  draft: "bg-text-tertiary",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function load() {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.access_token) {
          const data = await api.projects.list(session.access_token);
          setProjects(data);
        }
      } catch (e) {
        console.error("Failed to load projects:", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-medium text-foreground">Projects</h1>
        <Link
          href="/projects/new"
          className="text-sm text-accent hover:underline"
        >
          + New Project
        </Link>
      </div>

      {loading ? (
        <p className="text-text-secondary">Loading...</p>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-2 text-left text-xs font-medium text-text-tertiary">Name</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-tertiary">Tender #</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-tertiary">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-tertiary">Deadline</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-tertiary">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {projects.map((project) => (
              <tr
                key={project.id}
                onClick={() => router.push(`/projects/${project.id}`)}
                className="hover:bg-surface-hover transition-colors cursor-pointer"
              >
                <td className="px-4 py-3">
                  <span className="text-foreground hover:text-accent font-medium text-sm">
                    {project.name}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-text-secondary">{project.tender_number || "—"}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1.5 text-sm text-text-secondary">
                    <span className={`w-2 h-2 rounded-full ${STATUS_DOTS[project.status] || "bg-text-tertiary"}`} />
                    {project.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-text-secondary">
                  {project.deadline ? new Date(project.deadline).toLocaleDateString("de-DE") : "—"}
                </td>
                <td className="px-4 py-3 text-sm text-text-secondary">
                  {new Date(project.created_at).toLocaleDateString("de-DE")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
