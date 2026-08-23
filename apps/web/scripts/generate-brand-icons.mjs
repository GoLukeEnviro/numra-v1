#!/usr/bin/env node
/**
 * Regenerates the PWA icon PNGs in public/icons/ from the canonical brand mark
 * (src/app/icon.svg). See docs/brand/visual-identity.md §6.1.
 *
 * Renderer priority:
 *   1. Playwright package (`playwright` or `@playwright/test`) — dev envs, CI
 *   2. A locally installed ms-playwright Chromium via headless --screenshot
 *
 * Outputs:
 *   icon-192.png          192×192  (purpose: any)
 *   icon-512.png          512×512  (purpose: any)
 *   maskable-icon-512.png 512×512  (mark inside the 80 % maskable safe zone)
 */
import { promises as fs } from "node:fs";
import { spawn } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const svgPath = path.join(appDir, "src", "app", "icon.svg");
const outDir = path.join(appDir, "public", "icons");

const TARGETS = [
  { name: "icon-192.png", size: 192, maskable: false },
  { name: "icon-512.png", size: 512, maskable: false },
  { name: "maskable-icon-512.png", size: 512, maskable: true },
];

async function loadPlaywright() {
  for (const name of ["playwright", "@playwright/test"]) {
    try {
      return await import(name);
    } catch {
      // try next candidate
    }
  }
  return null;
}

async function findChromeExecutable() {
  const roots = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    path.join(os.homedir(), "AppData", "Local", "ms-playwright"),
  ].filter(Boolean);
  for (const root of roots) {
    let entries;
    try {
      entries = await fs.readdir(root);
    } catch {
      continue;
    }
    const builds = entries
      .filter((entry) => /^chromium-\d+$/.test(entry))
      .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
    for (const build of builds) {
      const exe = path.join(root, build, "chrome-win64", "chrome.exe");
      try {
        await fs.access(exe);
        return exe;
      } catch {
        // try next build
      }
    }
  }
  return null;
}

function htmlFor(size, maskable) {
  const dims = maskable ? Math.round(size * 0.8) : size;
  const bodyStyle = maskable
    ? "margin:0;width:100%;height:100%;background:#0B0B0F;display:flex;align-items:center;justify-content:center;"
    : "margin:0;";
  return `<!doctype html>
<html><head><style>html,body{${bodyStyle}}</style></head>
<body><img src="${pathToFileURL(svgPath).href}" width="${dims}" height="${dims}" style="display:block"></body></html>`;
}

function screenshotWithChrome(exe, htmlPath, pngPath, size) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      exe,
      [
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--run-all-compositor-stages-before-draw",
        "--force-device-scale-factor=1",
        `--window-size=${size},${size}`,
        `--screenshot=${pngPath}`,
        pathToFileURL(htmlPath).href,
      ],
      { stdio: "ignore" },
    );
    child.on("exit", (code) =>
      code === 0
        ? resolve()
        : reject(new Error(`Chromium exited with code ${code}`)),
    );
  });
}

async function screenshotWithPlaywright(module, htmlPath, pngPath, size) {
  const browser = await module.chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    await page.goto(pathToFileURL(htmlPath).href);
    await page.screenshot({ path: pngPath });
  } finally {
    await browser.close();
  }
}

const playwright = await loadPlaywright();
const chromeExe = await findChromeExecutable();
if (!playwright && !chromeExe) {
  console.error(
    "Kein Renderer verfügbar: `pnpm install` ausführen oder einen ms-playwright-Chromium installieren.",
  );
  process.exit(1);
}

const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "numra-icons-"));
try {
  await fs.mkdir(outDir, { recursive: true });
  for (const { name, size, maskable } of TARGETS) {
    const htmlPath = path.join(tempDir, `${name}.html`);
    const pngPath = path.join(tempDir, name);
    await fs.writeFile(htmlPath, htmlFor(size, maskable), "utf8");

    let rendered = false;
    if (playwright) {
      try {
        await screenshotWithPlaywright(playwright, htmlPath, pngPath, size);
        rendered = true;
      } catch {
        if (!chromeExe) throw new Error("Playwright-Rendering fehlgeschlagen und kein Chromium gefunden.");
      }
    }
    if (!rendered) {
      await screenshotWithChrome(chromeExe, htmlPath, pngPath, size);
    }

    await fs.copyFile(pngPath, path.join(outDir, name));
    console.log(`✓ ${name}`);
  }
} finally {
  await fs.rm(tempDir, { recursive: true, force: true });
}
