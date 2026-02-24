"use client";

import { useState, useRef, useCallback } from "react";
import { Upload, File, X, CheckCircle, AlertCircle } from "lucide-react";

const ACCEPTED_TYPES = [
  ".pdf", ".docx", ".xlsx", ".xml", ".xsl", ".txt", ".csv",
  ".html", ".json", ".x83", ".d83", ".zip", ".gaeb",
  ".aidocdef", ".aidoc", ".aiform",
];

interface DocumentUploaderProps {
  projectId: string;
  token: string;
  onUploadComplete: () => void;
}

interface UploadFile {
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
}

export default function DocumentUploader({ projectId, token, onUploadComplete }: DocumentUploaderProps) {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const additions = Array.from(newFiles).map((file) => ({
      file,
      status: "pending" as const,
    }));
    setFiles((prev) => [...prev, ...additions]);
  }, []);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(true);
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);

    const formData = new FormData();
    files.forEach((f) => {
      if (f.status === "pending") {
        formData.append("files", f.file);
      }
    });

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001/api";
      const res = await fetch(`${apiUrl}/projects/${projectId}/documents/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const result = await res.json();
      setFiles((prev) =>
        prev.map((f) =>
          f.status === "pending" ? { ...f, status: "done" as const } : f
        )
      );

      // Clear after brief delay so user sees the success state
      setTimeout(() => {
        setFiles([]);
        onUploadComplete();
      }, 1000);
    } catch (err) {
      setFiles((prev) =>
        prev.map((f) =>
          f.status === "pending"
            ? { ...f, status: "error" as const, error: "Upload failed" }
            : f
        )
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setIsDragging(false)}
        onClick={() => inputRef.current?.click()}
        className={`border border-dashed rounded-md p-8 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-accent bg-accent-light"
            : "border-border hover:border-text-tertiary hover:bg-surface"
        }`}
      >
        <Upload className="w-8 h-8 mx-auto mb-3 text-text-tertiary" />
        <p className="text-sm text-text-secondary mb-1">
          Drag and drop tender documents here, or click to browse
        </p>
        <p className="text-xs text-text-tertiary">
          PDF, DOCX, XLSX, XML, GAEB, ZIP and more
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(",")}
          onChange={(e) => e.target.files && addFiles(e.target.files)}
          className="hidden"
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="border border-border rounded-md divide-y divide-border">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-2">
              <File className="w-4 h-4 text-text-tertiary shrink-0" />
              <span className="text-sm flex-1 truncate text-foreground">{f.file.name}</span>
              <span className="text-xs text-text-tertiary">
                {(f.file.size / 1024).toFixed(0)} KB
              </span>
              {f.status === "done" && (
                <CheckCircle className="w-4 h-4 text-success" />
              )}
              {f.status === "error" && (
                <AlertCircle className="w-4 h-4 text-destructive" />
              )}
              {f.status === "pending" && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(i);
                  }}
                  className="text-text-tertiary hover:text-destructive"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Upload button */}
      {files.some((f) => f.status === "pending") && (
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="w-full bg-foreground text-white py-2 rounded-md hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {uploading
            ? "Uploading..."
            : `Upload ${files.filter((f) => f.status === "pending").length} file(s)`}
        </button>
      )}
    </div>
  );
}
