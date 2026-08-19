"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type ExportOut } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/utils";
import { Download, FileDown } from "lucide-react";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(0)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * PDF export for a completed report.
 *
 * `POST /v1/exports` is synchronous — it blocks until the PDF microservice has
 * genuinely rendered the file — so the button holds a real pending state for the
 * whole round trip instead of returning immediately and polling.
 *
 * The download itself is a plain same-origin link to
 * `/api/v1/exports/{id}/download`, which responds with raw PDF bytes and a
 * Content-Disposition header. It is deliberately not routed through the JSON
 * `request()` helper, which would mangle binary content.
 */
export function ExportPanel({ reportId }: { reportId: string }) {
  const [exports, setExports] = useState<ExportOut[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const loadExports = useCallback(async () => {
    try {
      const all = await api.exports.list();
      setExports(all.filter((e) => e.report_id === reportId));
    } catch {
      // A failed listing must not block the primary action — the panel still
      // renders its button, it just cannot show export history.
      setExports([]);
    }
  }, [reportId]);

  useEffect(() => {
    void loadExports();
  }, [loadExports]);

  async function handleExport() {
    setCreating(true);
    setError(null);
    try {
      const created = await api.exports.create({ report_id: reportId, export_type: "pdf" });
      if (created.status === "failed") {
        setError({
          code: created.error_code ?? "EXPORT_FAILED",
          message: "The PDF could not be rendered. You can try the export again.",
        });
      }
      await loadExports();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? { code: err.code, message: err.message }
          : { code: "NETWORK_ERROR", message: "Could not reach the server." },
      );
    } finally {
      setCreating(false);
    }
  }

  const completed = (exports ?? []).filter((e) => e.status === "complete");

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileDown className="h-5 w-5 text-gold" aria-hidden="true" />
          <CardTitle className="text-base">Export</CardTitle>
        </div>
        <CardDescription>
          Render this report as a PDF. The file is produced from the report exactly as it
          is stored — exporting never regenerates or changes the text.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={handleExport} loading={creating}>
          <Download className="h-4 w-4" aria-hidden="true" />
          {creating ? "Rendering PDF…" : "Export PDF"}
        </Button>
        {creating && (
          <p className="mt-2 text-xs text-muted" role="status" aria-live="polite">
            The PDF is rendered on the server; this usually takes a few seconds.
          </p>
        )}

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
          >
            <span className="mr-1.5 rounded bg-black/25 px-1.5 py-0.5 font-mono text-xs">
              {error.code}
            </span>
            {error.message}
          </div>
        )}

        {completed.length > 0 && (
          <div className="mt-6 border-t border-white/10 pt-5">
            <p className="mb-3 text-xs uppercase tracking-wider text-muted">Available files</p>
            <ul className="flex flex-col gap-2">
              {completed.map((exp) => (
                <li
                  key={exp.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-surface-2 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-ivory">
                      PDF <span className="text-muted">· {formatBytes(exp.file_size_bytes)}</span>
                    </p>
                    <p className="text-xs text-muted">{formatDateTime(exp.created_at)}</p>
                  </div>
                  <a
                    href={api.exports.downloadUrl(exp.id)}
                    className="inline-flex h-8 items-center gap-2 rounded-lg border border-white/10 bg-surface px-3 text-xs font-medium text-ivory transition-colors hover:border-gold/50"
                  >
                    <Download className="h-3.5 w-3.5" aria-hidden="true" />
                    Download
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {exports !== null && completed.length === 0 && !creating && (
          <p className="mt-4 text-xs text-muted">
            No PDF has been rendered for this report yet.
          </p>
        )}

        {(exports ?? []).some((e) => e.status === "failed") && (
          <p className="mt-3 text-xs text-muted">
            <Badge variant="neutral">Earlier attempt failed</Badge>{" "}
            A previous export of this report did not complete.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
