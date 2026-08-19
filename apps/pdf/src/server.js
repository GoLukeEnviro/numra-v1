import { existsSync } from "node:fs";

import express from "express";
import { chromium } from "playwright";

import { resolveLaunchOptions } from "./chromium-path.js";
import { renderReportHtml } from "./template.js";

const PORT = process.env.PORT || 4300;
const INTERNAL_TOKEN = process.env.PDF_INTERNAL_TOKEN;
const MAX_BODY_BYTES = 20 * 1024 * 1024; // 20MB — a full ULTIMATE report JSON payload

if (!INTERNAL_TOKEN) {
  // Fail loudly at startup rather than silently accepting unauthenticated requests.
  // eslint-disable-next-line no-console
  console.error("FATAL: PDF_INTERNAL_TOKEN is not set. Refusing to start.");
  process.exit(1);
}

const app = express();
app.use(express.json({ limit: MAX_BODY_BYTES }));

let browserPromise;
function getBrowser() {
  if (!browserPromise) {
    browserPromise = chromium.launch(resolveLaunchOptions(existsSync));
  }
  return browserPromise;
}

app.get("/health/live", (_req, res) => {
  res.json({ status: "live" });
});

app.get("/health/ready", async (_req, res) => {
  try {
    await getBrowser();
    res.json({ status: "healthy", chromium: "healthy" });
  } catch (error) {
    res.status(503).json({ status: "unhealthy", chromium: "unhealthy", error: String(error) });
  }
});

function requireInternalAuth(req, res, next) {
  const header = req.header("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice("Bearer ".length) : null;
  // Constant-time-ish comparison is unnecessary here (not a password), but avoid
  // short-circuit leaking timing on a static, non-secret-adjacent internal token.
  if (!token || token !== INTERNAL_TOKEN) {
    res.status(401).json({ code: "PDF_UNAUTHORIZED", message: "missing or invalid internal token" });
    return;
  }
  next();
}

/**
 * Renders a NUMRA report to PDF. This endpoint NEVER accepts or navigates to a
 * caller-supplied URL (no SSRF surface) — it only ever renders HTML built in-process
 * from a validated JSON payload the caller already fetched from the NUMRA API.
 */
app.post("/render/report", requireInternalAuth, async (req, res) => {
  const { report, profile, person } = req.body || {};

  if (!report || !Array.isArray(report.sections) || report.sections.length === 0) {
    res.status(422).json({ code: "PDF_RENDER_FAILED", message: "report.sections is required and must be non-empty" });
    return;
  }

  let page;
  try {
    const browser = await getBrowser();
    const context = await browser.newContext();
    page = await context.newPage();

    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });

    const html = renderReportHtml({ report, profile, person });
    await page.setContent(html, { waitUntil: "load" });

    if (errors.length > 0) {
      throw new Error(`Runtime errors while rendering: ${errors.join("; ")}`);
    }

    const pdfBuffer = await page.pdf({
      format: "A4",
      printBackground: true,
      margin: { top: "24mm", bottom: "24mm", left: "18mm", right: "18mm" },
    });

    await context.close();

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", "attachment; filename=numra-report.pdf");
    res.send(pdfBuffer);
  } catch (error) {
    if (page) {
      await page.context().close().catch(() => {});
    }
    res.status(500).json({ code: "PDF_RENDER_FAILED", message: String(error) });
  }
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`NUMRA PDF service listening on :${PORT}`);
});

export { app };
