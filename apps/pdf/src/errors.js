/**
 * Failure responses for the PDF service. The response body is a fixed, generic
 * code/message pair: the underlying error (Chromium launch paths, Playwright
 * stack traces, page runtime errors) is written to the service log only and never
 * sent to the caller.
 */
export function sendFailure(res, status, body, context, error, log = console.error) {
  log(`[pdf] ${context}:`, error);
  res.status(status).json(body);
}

export const NOT_READY_BODY = Object.freeze({ status: "unhealthy", chromium: "unhealthy" });

export const RENDER_FAILED_BODY = Object.freeze({
  code: "PDF_RENDER_FAILED",
  message: "PDF rendering failed",
});
