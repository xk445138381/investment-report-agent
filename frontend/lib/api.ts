/**
 * API client for the investment report agent backend.
 * Override with NEXT_PUBLIC_API_URL in deployed environments.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalizedPath}`;
}

export function backendHealthUrl(): string {
  return API_BASE.replace(/\/api\/v1\/?$/, "/health");
}

export interface GenerateRequest {
  ticker: string;
  report_type?: string;
  template_id?: string;
}

export interface GenerateResponse {
  task_id: string;
  status: string;
}

export interface TaskStatus {
  task_id: string;
  status: "queued" | "running" | "completed" | "failed";
  current_phase?: string;
  progress_pct: number;
  started_at?: string;
}

export type SSECallback = (event: string, data: string) => void;

/** Start a report generation task */
export async function generateReport(params: GenerateRequest): Promise<GenerateResponse> {
  const res = await fetch(apiUrl("/report/generate"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ticker: params.ticker,
      report_type: params.report_type || "deep_dive",
      template_id: params.template_id || "deep_dive_default",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || "Failed to generate report");
  }
  return res.json();
}

/** Poll task status */
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const res = await fetch(apiUrl(`/report/${taskId}/status`));
  if (!res.ok) throw new Error("Task not found");
  return res.json();
}

/** Connect to SSE progress stream. Returns an abort function. */
export function streamProgress(taskId: string, onEvent: SSECallback): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(apiUrl(`/report/${taskId}/stream`), {
        signal: controller.signal,
        headers: { Accept: "text/event-stream" },
      });

      if (!res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventType = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            onEvent(eventType, line.slice(6).trim());
          }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") return;
      onEvent("error", `Connection failed: ${e}`);
    }
  })();

  return () => controller.abort();
}

/** Check if the backend is reachable */
export async function healthCheck(): Promise<boolean> {
  try {
    const res = await fetch(backendHealthUrl(), { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}
