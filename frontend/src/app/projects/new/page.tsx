"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase";

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tenderNumber, setTenderNumber] = useState("");
  const [deadline, setDeadline] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);

    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const project = await api.projects.create(
        {
          name,
          description,
          tender_number: tenderNumber,
          deadline: deadline || undefined,
        },
        session.access_token
      );

      router.push(`/projects/${project.id}`);
    } catch (e) {
      console.error("Failed to create project:", e);
      alert("Failed to create project");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-medium text-foreground mb-8">New Project</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm text-text-secondary mb-1">
            Project Name *
          </label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:border-accent transition-colors"
            placeholder="e.g., Vergabe Schweißarbeiten 2025"
          />
        </div>

        <div>
          <label className="block text-sm text-text-secondary mb-1">
            Tender Number
          </label>
          <input
            type="text"
            value={tenderNumber}
            onChange={(e) => setTenderNumber(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:border-accent transition-colors"
            placeholder="e.g., DTAD_23395424"
          />
        </div>

        <div>
          <label className="block text-sm text-text-secondary mb-1">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:border-accent transition-colors"
            placeholder="Brief description of the tender..."
          />
        </div>

        <div>
          <label className="block text-sm text-text-secondary mb-1">
            Submission Deadline
          </label>
          <input
            type="datetime-local"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:border-accent transition-colors"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting || !name}
            className="bg-foreground text-white px-6 py-2 rounded-md hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? "Creating..." : "Create Project"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-6 py-2 text-text-secondary hover:text-foreground transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
