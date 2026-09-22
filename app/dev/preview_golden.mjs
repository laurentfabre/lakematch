// Read-only layout check of the packaged synthetic screen, not campaign acceptance.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.LAKEMATCH_PLAYWRIGHT_MODULE || "playwright");
const [url, output] = process.argv.slice(2);
if (!url || !output) throw new Error("Usage: preview_golden.mjs <loopback-url> <output-directory>");
const parsed = new URL(url);
if (parsed.hostname !== "127.0.0.1") throw new Error("Local development preview only");
const browser = await chromium.launch({ headless: true, executablePath: process.env.LAKEMATCH_CHROMIUM_EXECUTABLE });
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.setDefaultTimeout(10000);
  page.on("pageerror", e => errors.push(e.message));
  const requests = [];
  page.on("request", request => requests.push({ method: request.method(), url: request.url() }));
  await page.goto(url + "/#golden-records");
  await page.getByRole("heading", { name: "Cedar Components — reviewed name", exact: true }).waitFor();
  await page.screenshot({ path: path.join(output, "golden-desktop.png"), fullPage: true });
  await page.getByLabel("Publication", { exact: true }).selectOption("first");
  await page.getByRole("heading", { name: "Cedar Components SA", exact: true }).waitFor();
  await page.getByText("Earlier publication.", { exact: false }).waitFor();
  await page.screenshot({ path: path.join(output, "golden-history.png"), fullPage: true });
  await page.getByLabel("Company", { exact: true }).selectOption({ label: "Atlas Supplies SAS · FR" });
  await page.getByLabel("Publication", { exact: true }).selectOption("second");
  await page.getByRole("heading", { name: "Atlas Supplies SAS", exact: true }).waitFor();
  await page.getByText("A003 · v2 · Deleted", { exact: true }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(output, "golden-mobile.png"), fullPage: true });
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  if (!fits) throw new Error("Mobile page overflows horizontally");
  if (requests.some(r => r.method !== "GET" || /\/api\/(queue|statistics|reviews)/.test(r.url))) {
    throw new Error("The synthetic screen accessed review data or performed a write");
  }
  if (errors.length) throw new Error(errors.join("\n"));
  fs.writeFileSync(path.join(output, "preview.json"), JSON.stringify({
    kind: "local_development_preview", acceptance_gate: "pending_authorized_experiment",
    app: "APX 0.3.8", corpus_access: false, remote_calls: false, review_writes: false,
    desktop: [1440, 1100], mobile: [390, 844], page_errors: errors, mobile_fits: fits,
    views: ["approved_name_override", "earlier_publication", "deleted_source"],
  }, null, 2) + "\n");
} finally {
  await browser.close();
}
