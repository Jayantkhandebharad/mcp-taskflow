// The phase-4 "done when": the whole flow, with a mouse — scripted.
//
// CLAUDE.md: "No manual clicking that isn't also a script." This is that
// script. It drives a real headless Chrome through every screen against the
// running backend and the seed data, checks what a person would check, and
// leaves the database as it found it. Run it with:
//
//     npm run walkthrough           # from frontend/, with both servers up
//
// It needs: the backend on :8000 with the seed loaded, `npm run dev` on
// :5173, and Google Chrome (or set CHROME_BIN). Screenshots land in
// ../scratch/screenshots/ (gitignored).
//
// Why not Playwright or Cypress? Zero dependencies: Node 22+ ships `fetch`
// and a `WebSocket` client, and Chrome speaks the DevTools Protocol (CDP)
// over a WebSocket. Everything below is "send a JSON command, wait for the
// reply". A test framework would hide exactly the part worth seeing.
//
// This is NOT a substitute for pytest on the backend. It proves the UI
// wires the routes together; the rules themselves are tested where they
// live (fastapi-backend/tests).

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const APP = process.env.FRONTEND_URL ?? "http://localhost:5173";
const DEBUG_PORT = 9222;
const SHOTS = fileURLToPath(new URL("../../scratch/screenshots/", import.meta.url));
mkdirSync(SHOTS, { recursive: true });

// ── Launch Chrome ────────────────────────────────────────────────────────────

const candidates = [
  process.env.CHROME_BIN,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);
const chromeBin = candidates.find((p) => existsSync(p));
if (!chromeBin) {
  console.error("No Chrome found. Set CHROME_BIN to a Chrome/Chromium binary.");
  process.exit(2);
}
const chrome = spawn(
  chromeBin,
  [
    "--headless=new",
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${join(tmpdir(), "taskflow-walkthrough-profile")}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,900",
    "about:blank",
  ],
  { stdio: "ignore" },
);
process.on("exit", () => chrome.kill());

// Poll until the debugging port answers; Chrome takes a second or two.
let page;
for (let i = 0; i < 50 && !page; i++) {
  try {
    const targets = await (await fetch(`http://localhost:${DEBUG_PORT}/json`)).json();
    page = targets.find((t) => t.type === "page");
  } catch {
    await sleep(200);
  }
}
if (!page) fail("Chrome did not start");

// ── A tiny CDP client ────────────────────────────────────────────────────────

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve) => (ws.onopen = resolve));
let nextId = 0;
const pending = new Map();
const consoleErrors = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
  // Anything the page logs as an error, or throws, fails the run at the end.
  if (msg.method === "Runtime.exceptionThrown") {
    consoleErrors.push(msg.params.exceptionDetails.exception?.description ?? msg.params.exceptionDetails.text);
  }
  if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
    consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
  }
};
const send = (method, params = {}) =>
  new Promise((resolve) => {
    const id = ++nextId;
    pending.set(id, resolve);
    ws.send(JSON.stringify({ id, method, params }));
  });
await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });

// ── Helpers ──────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/** Run JavaScript in the page and return its (JSON-able) result. */
async function evaluate(expression) {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) {
    throw new Error(`in page: ${r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text}`);
  }
  return r.result.result.value;
}

async function nav(path) {
  await send("Page.navigate", { url: APP + path });
  await sleep(300);
}

/** Wait until an expression is truthy in the page. Polling, not sleeping. */
async function waitFor(expression, label, timeoutMs = 10_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await evaluate(expression)) return;
    await sleep(100);
  }
  throw new Error(`timed out waiting for ${label}`);
}
const waitText = (text) => waitFor(`document.body.innerText.includes(${JSON.stringify(text)})`, `text "${text}"`);
const waitSelector = (sel) => waitFor(`!!document.querySelector(${JSON.stringify(sel)})`, `selector ${sel}`);
const hasText = (text) => evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`);

/**
 * Type into a React-controlled input. Setting `el.value` directly does not
 * fire React's onChange (React tracks the value and ignores programmatic
 * writes), so we focus the element and insert text through Chrome's real
 * input pipeline, the same path a keyboard takes.
 */
async function type(selector, text) {
  await waitSelector(selector);
  await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.focus(); el.select?.(); })()`);
  await send("Input.insertText", { text });
}

/** Set a <select>. For selects, a dispatched 'change' event is enough for React. */
async function choose(selector, value) {
  await waitSelector(selector);
  await evaluate(
    `(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.value = ${JSON.stringify(value)}; el.dispatchEvent(new Event("change", { bubbles: true })); })()`,
  );
}

/** Click the first element of `tag` whose trimmed text is exactly `text`. */
async function clickText(tag, text) {
  const find = `[...document.querySelectorAll(${JSON.stringify(tag)})].find(e => e.textContent.trim() === ${JSON.stringify(text)})`;
  await waitFor(`!!(${find})`, `${tag} "${text}"`);
  await evaluate(`(${find}).click()`);
}

async function screenshot(name) {
  await sleep(250); // let the last render paint
  const r = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(SHOTS, `${name}.png`), Buffer.from(r.result.data, "base64"));
}

let failures = 0;
function check(condition, label) {
  console.log(`${condition ? "  ok " : "FAIL "} ${label}`);
  if (!condition) failures++;
}
function fail(message) {
  console.error("FAIL", message);
  process.exit(1);
}

async function login(email, password) {
  await waitText("Log in");
  await type("input[type=email]", email);
  await type("input[type=password]", password);
  await evaluate(`document.querySelector("button[type=submit]").click()`);
}

// ── The walkthrough ──────────────────────────────────────────────────────────

const TITLE = "Walkthrough smoke task";

try {
  // 1. Login — wrong password shows the backend's sentence and stays put.
  await nav("/");
  await screenshot("1-login");
  await login("alice@example.com", "not-the-password");
  await waitText("Invalid email or password");
  check((await evaluate("location.pathname")) === "/login", "wrong password: 401 sentence shown, still on /login");
  await type("input[type=password]", "password");
  await evaluate(`document.querySelector("button[type=submit]").click()`);

  // 2. Projects — Alice is admin of both seed projects; /me/tasks lists hers.
  await waitText("Assigned to me");
  check(await hasText("TaskFlow Web"), "projects: WEB listed");
  check(await hasText("TaskFlow API"), "projects: API listed");
  await screenshot("2-projects");

  // 3. Board — move a card, filter server-side, create a task.
  await evaluate(`document.querySelector('a[href="/projects/WEB"]').click()`);
  await waitSelector("select[aria-label^='Status of']");
  await screenshot("3-board");
  const cardRef = await evaluate(`document.querySelector("select[aria-label^='Status of']").getAttribute("aria-label").slice("Status of ".length)`);
  const cardSelect = `select[aria-label='Status of ${cardRef}']`;
  const originalStatus = await evaluate(`document.querySelector("${cardSelect}").value`);
  await choose(cardSelect, "in_review");
  await waitFor(`document.querySelector("${cardSelect}")?.value === "in_review"`, `${cardRef} moved`);
  check(true, `board: ${cardRef} moved ${originalStatus} → in_review via PATCH`);
  await choose(cardSelect, originalStatus);
  await waitFor(`document.querySelector("${cardSelect}")?.value === "${originalStatus}"`, `${cardRef} moved back`);

  const total = await evaluate(`document.querySelectorAll("select[aria-label^='Status of']").length`);
  await evaluate(`[...document.querySelectorAll("label")].find(l => l.textContent.includes("Only overdue")).querySelector("input").click()`);
  await sleep(700);
  const overdue = await evaluate(`document.querySelectorAll("select[aria-label^='Status of']").length`);
  check(overdue < total, `board: "Only overdue" filter asked the API (${overdue} of ${total} shown)`);
  await screenshot("3b-board-overdue");
  await evaluate(`[...document.querySelectorAll("label")].find(l => l.textContent.includes("Only overdue")).querySelector("input").click()`);
  await sleep(500);

  await type("form input[maxlength='500']", TITLE);
  await clickText("button", "Add task");
  await waitText(TITLE);
  check(true, "board: task created (201) and appears in To do");
  await screenshot("3c-board-new-task");

  // 4. Task detail — a diff-only PATCH, then a comment.
  await evaluate(`[...document.querySelectorAll("a")].find(a => a.textContent.includes(${JSON.stringify(TITLE)})).click()`);
  await waitSelector("textarea[placeholder]");
  const ref = (await evaluate("location.pathname")).replace("/tasks/", "");
  const saveDisabled = () => evaluate(`[...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Save").disabled`);
  check(await saveDisabled(), `task ${ref}: Save disabled while nothing changed`);
  const bobId = await evaluate(`[...document.querySelectorAll("form select")[2].options].find(o => o.text.includes("Bob")).value`);
  await evaluate(`(() => { const el = document.querySelectorAll("form select")[2]; el.value = ${JSON.stringify(bobId)}; el.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await evaluate(`(() => { const el = document.querySelectorAll("form select")[1]; el.value = "high"; el.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await clickText("button", "Save");
  await waitFor(`document.querySelectorAll("form select")[2].selectedOptions[0].text.includes("Bob") && ${"[...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Save').disabled"}`, "save to land");
  check(true, `task ${ref}: assignee + priority saved, form refilled from the response`);
  await type("textarea[placeholder]", "Reassigned by the walkthrough.");
  await clickText("button", "Comment");
  await waitText("Reassigned by the walkthrough.");
  check(true, `task ${ref}: comment posted and listed`);
  await screenshot("4-task");

  // Delete it (Alice is admin) — the confirm() dialog is auto-accepted.
  await evaluate("window.confirm = () => true");
  await clickText("button", "Delete task");
  await waitFor(`location.pathname === "/projects/WEB"`, "redirect to the board");
  await waitSelector("select[aria-label^='Status of']");
  check(!(await hasText(TITLE)), `task ${ref}: deleted (204), back on the board without it`);

  // 5. Members — the last-admin 409, add, remove.
  await clickText("a", "Members");
  await waitText("Add a member");
  await screenshot("5-members");
  await evaluate(`[...document.querySelectorAll("li")].find(li => li.textContent.includes("(you)")).querySelector("button").click()`);
  await waitSelector("[role=alert]");
  check((await evaluate(`document.querySelector("[role=alert]").textContent`)).includes("last admin"), "members: removing the last admin shows the 409 sentence");
  await screenshot("5b-members-last-admin");
  await type("input[type=email]", "carol@example.com");
  await clickText("button", "Add");
  await waitText("Carol");
  check(true, "members: Carol added (201)");
  await evaluate(`[...document.querySelectorAll("li")].find(li => li.textContent.includes("Carol")).querySelector("button").click()`);
  await waitFor(`!document.body.innerText.includes("Carol")`, "Carol removed");
  check(true, "members: Carol removed (204)");

  // 6. Bob is a plain member: things hidden, backend still the rule.
  await clickText("button", "Log out");
  await waitText("Log in");
  check((await evaluate(`localStorage.getItem("taskflow.token")`)) === null, "logout: token gone from localStorage");
  await login("bob@example.com", "password");
  await waitText("Assigned to me");
  await nav("/projects/WEB");
  await waitSelector("select[aria-label^='Status of']");
  check(!(await evaluate(`!![...document.querySelectorAll("a")].find(a => a.textContent.trim() === "Members")`)), "bob: no Members link on the board");
  await nav("/projects/WEB/members");
  await waitText("Only an admin");
  check(true, "bob: members page by URL is read-only, no form");
  await screenshot("6-bob-members");
  await nav("/projects/API");
  await waitSelector("[role=alert]");
  check((await evaluate(`document.querySelector("[role=alert]").textContent`)).includes("not a member"), "bob: project he's not in shows the backend's 403 sentence");

  // 7. A token that no longer verifies bounces to login and is forgotten.
  await evaluate(`localStorage.setItem("taskflow.token", "not-a-jwt")`);
  await nav("/");
  await waitText("Log in");
  check((await evaluate(`localStorage.getItem("taskflow.token")`)) === null, "bad token: 401 on /auth/me → login page, token cleared");
} catch (error) {
  await screenshot("zz-failure");
  console.error("FAIL", error.message);
  console.error("page text:\n" + (await evaluate("document.body.innerText")).slice(0, 600));
  failures++;
}

check(consoleErrors.length === 0, `no console errors${consoleErrors.length ? ": " + consoleErrors.join(" | ") : ""}`);
console.log(failures === 0 ? `\nPASS — screenshots in ${SHOTS}` : `\n${failures} check(s) FAILED`);
ws.close();
process.exit(failures === 0 ? 0 : 1);
