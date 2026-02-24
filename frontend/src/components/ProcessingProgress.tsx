"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Loader2, CheckCircle, XCircle, Play } from "lucide-react";
import { api, type ProcessingJob } from "@/lib/api";

interface ProcessingProgressProps {
  projectId: string;
  token: string;
  documentCount: number;
  onComplete: () => void;
  onProgress?: () => void;
}

export default function ProcessingProgress({
  projectId,
  token,
  documentCount,
  onComplete,
  onProgress,
}: ProcessingProgressProps) {
  const [job, setJob] = useState<ProcessingJob | null>(null);
  const [running, setRunning] = useState(false);
  const lastProcessedRef = useRef(0);

  // On mount, check if there's an active job to resume polling
  useEffect(() => {
    let cancelled = false;
    async function checkActive() {
      try {
        const result = await api.processing.activeJob(projectId, token);
        if (!cancelled && result.active && result.job) {
          setJob(result.job);
          setRunning(true);
          pollJob(result.job.id);
        }
      } catch {
        // ignore — no active job
      }
    }
    checkActive();
    return () => { cancelled = true; };
  }, [projectId, token]);

  const pollJob = useCallback(
    async (jobId: string) => {
      const interval = setInterval(async () => {
        try {
          const status = await api.processing.jobStatus(jobId, token);
          setJob(status);

          // Notify parent when a new document finishes processing
          if (status.processed_documents > lastProcessedRef.current) {
            lastProcessedRef.current = status.processed_documents;
            onProgress?.();
          }

          if (status.status === "completed" || status.status === "failed") {
            clearInterval(interval);
            setRunning(false);
            lastProcessedRef.current = 0;
            if (status.status === "completed") {
              onComplete();
            }
          }
        } catch {
          clearInterval(interval);
          setRunning(false);
        }
      }, 1500);
      return () => clearInterval(interval);
    },
    [token, onComplete]
  );

  async function startProcessing(full = false) {
    setRunning(true);
    setJob(null);
    try {
      const { job_id } = await api.processing.start(projectId, token, full);
      setJob({
        id: job_id,
        status: "running",
        progress: 0,
        current_step: "Starting extraction...",
        total_documents: documentCount,
        processed_documents: 0,
        error_message: null,
      });
      pollJob(job_id);
    } catch (err) {
      setRunning(false);
      setJob({
        id: "",
        status: "failed",
        progress: 0,
        current_step: "",
        total_documents: 0,
        processed_documents: 0,
        error_message: String(err),
      });
    }
  }

  const progressPct = job ? Math.round((job.progress || 0) * 100) : 0;

  return (
    <div className="space-y-3">
      {/* Control buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => startProcessing(false)}
          disabled={running || documentCount === 0}
          className="flex items-center gap-2 bg-foreground text-white px-4 py-2 rounded-md hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {running ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {running ? "Processing..." : "Run AI Extraction"}
        </button>
        {!running && documentCount > 0 && (
          <button
            onClick={() => startProcessing(true)}
            className="text-sm text-text-secondary hover:text-foreground px-3 py-2 transition-colors"
          >
            Force Full Re-scan
          </button>
        )}
      </div>

      {/* Progress display */}
      {job && (
        <div className="bg-surface border border-border rounded-md p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {job.status === "running" && (
                <Loader2 className="w-4 h-4 text-foreground animate-spin" />
              )}
              {job.status === "completed" && (
                <CheckCircle className="w-4 h-4 text-success" />
              )}
              {job.status === "failed" && (
                <XCircle className="w-4 h-4 text-destructive" />
              )}
              <span className="text-sm text-foreground">
                {job.status === "completed"
                  ? "Extraction complete"
                  : job.status === "failed"
                  ? "Extraction failed"
                  : job.current_step || "Processing..."}
              </span>
            </div>
            {job.total_documents > 0 && (
              <span className="text-xs text-text-secondary">
                {job.processed_documents}/{job.total_documents} documents
              </span>
            )}
          </div>

          {job.status === "running" && (
            <div className="w-full bg-surface-active rounded-full h-1">
              <div
                className="bg-foreground rounded-full h-1 transition-all duration-500"
                style={{ width: `${Math.max(progressPct, 2)}%` }}
              />
            </div>
          )}

          {job.error_message && (
            <p className="text-xs text-destructive mt-2">{job.error_message}</p>
          )}
        </div>
      )}

      {documentCount === 0 && !running && (
        <p className="text-sm text-text-tertiary">
          Upload documents first before running AI extraction.
        </p>
      )}
    </div>
  );
}
