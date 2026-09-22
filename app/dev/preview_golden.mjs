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
  const comparison = page.getByRole("region", { name: "Do the source records agree?", exact: true });
  await comparison.getByText("Human review required", { exact: true }).waitFor();
  await comparison.getByText("No model score · no automatic merge", { exact: true }).waitFor();
  if (await comparison.locator(".match-field").count() !== 7) throw new Error("Seven comparison fields required");
  const street = comparison.locator(".match-field").filter({ has: page.getByText("Street address", { exact: true }) });
  await street.locator("summary").focus();
  await page.keyboard.press("Space");
  if (await street.getAttribute("open") === null) throw new Error("Keyboard disclosure did not open");
  await street.getByText("99 Updated Example Avenue", { exact: true }).first().waitFor();
  await page.screenshot({ path: path.join(output, "golden-desktop.png"), fullPage: true });
  await page.getByLabel("Publication", { exact: true }).selectOption("first");
  await page.getByRole("heading", { name: "Cedar Components SA", exact: true }).waitFor();
  await page.getByText("Earlier publication.", { exact: false }).waitFor();
  await street.locator("summary").click();
  await street.getByText("10 Example Avenue", { exact: true }).waitFor();
  await street.getByText("99 Updated Example Avenue", { exact: true }).waitFor();
  await page.screenshot({ path: path.join(output, "golden-history.png"), fullPage: true });
  await page.getByLabel("Company", { exact: true }).selectOption({ label: "Harbor Industrial Ltd · GB" });
  await comparison.getByText("Registration identifiers disagree in the same jurisdiction; resolve the conflict first.", { exact: true }).first().waitFor();
  await comparison.getByText("TEST-GB-004", { exact: true }).waitFor();
  await comparison.getByText("TEST-GB-005", { exact: true }).waitFor();
  await comparison.screenshot({ path: path.join(output, "comparison-conflict.png") });
  await page.getByLabel("Company", { exact: true }).selectOption({ label: "Cedar Logistics SAS · FR" });
  await page.getByRole("heading", { name: "Cedar Logistics SAS", exact: true }).waitFor();
  const name = comparison.locator(".match-field").filter({ has: page.getByText("Legal name", { exact: true }) });
  await name.locator("summary").click();
  await name.getByText("Agree after normalization", { exact: true }).waitFor();
  if (await name.getByText("Compared as: cedar logistics", { exact: true }).count() !== 2) throw new Error("Normalized values are not shown for both sources");
  await comparison.screenshot({ path: path.join(output, "comparison-normalization.png") });
  await page.getByLabel("Company", { exact: true }).selectOption({ label: "Atlas Supplies SAS · FR" });
  await page.getByLabel("Publication", { exact: true }).selectOption("second");
  await page.getByRole("heading", { name: "Atlas Supplies SAS", exact: true }).waitFor();
  await page.getByRole("region", { name: "Source crosswalk", exact: true }).getByText("A003 · v2 · Deleted", { exact: true }).waitFor();
  await comparison.getByText("Excluded from new matching", { exact: true }).waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(output, "golden-mobile.png"), fullPage: true });
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  if (!fits) throw new Error("Mobile page overflows horizontally");
  // A failed demo read must be visible and recover without touching review data.
  await page.route("**/api/demo/golden-records", route => route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Preview failure fixture"}' }));
  await page.reload();
  await page.getByRole("alert").getByText("The company demo could not load.", { exact: false }).waitFor();
  await page.unroute("**/api/demo/golden-records");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await page.getByRole("heading", { name: "Cedar Components — reviewed name", exact: true }).waitFor();
  if (requests.some(r => r.method !== "GET" || /\/api\/(queue|statistics|reviews)/.test(r.url))) {
    throw new Error("The synthetic screen accessed review data or performed a write");
  }
  if (errors.length) throw new Error(errors.join("\n"));
  fs.writeFileSync(path.join(output, "preview.json"), JSON.stringify({
    kind: "local_development_preview", acceptance_gate: "determined_by_campaign_runner",
    app: "APX 0.3.8", corpus_access: false, remote_calls: false, review_writes: false,
    desktop: [1440, 1100], mobile: [390, 844], page_errors: errors, mobile_fits: fits,
    views: ["approved_name_override", "earlier_publication", "deleted_source", "identifier_conflict", "normalized_name_agreement"],
    keyboard_disclosure: true, error_recovery: true, comparison_fields: 7,
  }, null, 2) + "\n");
} finally {
  await browser.close();
}
