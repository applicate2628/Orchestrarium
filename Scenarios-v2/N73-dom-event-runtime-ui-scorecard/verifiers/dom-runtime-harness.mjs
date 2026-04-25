import { writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [bundleRootArg, metricsPathArg] = process.argv.slice(2);
const bundleRoot = path.resolve(bundleRootArg);
const metricsPath = path.resolve(metricsPathArg);
const failures = [];

function fail(id, detail) {
  failures.push({ id, detail });
}

function assertCondition(condition, id, detail) {
  if (!condition) {
    fail(id, detail);
  }
}

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map();
    this.children = [];
    this.parentNode = null;
    this.listeners = new Map();
    this._text = "";
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  append(...children) {
    for (const child of children) {
      if (typeof child === "string") {
        const text = new FakeElement("#text");
        text._text = child;
        this.appendChild(text);
      } else {
        this.appendChild(child);
      }
    }
  }

  replaceChildren(...children) {
    this.children = [];
    this._text = "";
    this.append(...children);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  addEventListener(type, listener) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(listener);
  }

  dispatchEvent(event) {
    event.target ??= this;
    event.currentTarget = this;
    event.defaultPrevented ??= false;
    event.preventDefault ??= () => {
      event.defaultPrevented = true;
    };
    for (const listener of this.listeners.get(event.type) ?? []) {
      listener.call(this, event);
    }
    return !event.defaultPrevented;
  }

  set innerHTML(html) {
    this.children = parseFragment(html, this);
    this._text = "";
  }

  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.children = [];
    this._text = String(value);
  }

  get className() {
    return this.getAttribute("class") ?? "";
  }

  set className(value) {
    this.setAttribute("class", value);
  }

  get disabled() {
    return this.hasAttribute("disabled");
  }

  set disabled(value) {
    if (value) {
      this.setAttribute("disabled", "");
    } else {
      this.removeAttribute("disabled");
    }
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  querySelectorAll(selector) {
    const parts = selector.trim().split(/\s+/);
    let current = [this];
    for (const part of parts) {
      const next = [];
      for (const node of current) {
        next.push(...node.descendants().filter((candidate) => candidate.matches(part)));
      }
      current = next;
    }
    return current;
  }

  descendants() {
    const result = [];
    for (const child of this.children) {
      if (child.tagName !== "#TEXT") {
        result.push(child);
        result.push(...child.descendants());
      }
    }
    return result;
  }

  matches(selector) {
    if (selector.startsWith("[")) {
      const match = selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
      if (!match) {
        return false;
      }
      const [, name, value] = match;
      if (!this.hasAttribute(name)) {
        return false;
      }
      return value === undefined || this.getAttribute(name) === value;
    }
    if (selector.startsWith(".")) {
      return this.className.split(/\s+/).includes(selector.slice(1));
    }
    if (selector.startsWith("#")) {
      return this.getAttribute("id") === selector.slice(1);
    }
    return this.tagName.toLowerCase() === selector.toLowerCase();
  }
}

class FakeDocument {
  createElement(tagName) {
    return new FakeElement(tagName);
  }

  createTextNode(text) {
    const node = new FakeElement("#text");
    node.textContent = text;
    return node;
  }
}

function parseFragment(html, root) {
  const stack = [root];
  const topLevel = [];
  const tokenPattern = /<[^>]+>|[^<]+/g;
  for (const token of html.match(tokenPattern) ?? []) {
    if (token.startsWith("</")) {
      if (stack.length > 1) {
        stack.pop();
      }
      continue;
    }
    if (token.startsWith("<")) {
      const open = token.match(/^<\s*([A-Za-z0-9-]+)/);
      if (!open) {
        continue;
      }
      const element = new FakeElement(open[1]);
      const attrText = token.replace(/^<\s*[A-Za-z0-9-]+/, "").replace(/\/?\s*>$/, "");
      const attrPattern = /([:@A-Za-z0-9_-]+)(?:="([^"]*)")?/g;
      for (const attr of attrText.matchAll(attrPattern)) {
        element.setAttribute(attr[1], attr[2] ?? "");
      }
      stack[stack.length - 1].appendChild(element);
      if (stack.length === 1) {
        topLevel.push(element);
      }
      if (!token.endsWith("/>") && !["input", "br", "hr", "img", "meta", "link"].includes(open[1].toLowerCase())) {
        stack.push(element);
      }
      continue;
    }
    const text = token.replace(/\s+/g, " ").trim();
    if (text) {
      stack[stack.length - 1]._text += text;
    }
  }
  return topLevel;
}

function click(element) {
  element.dispatchEvent({ type: "click" });
}

function keydown(element, key) {
  element.dispatchEvent({ type: "keydown", key });
}

function textOf(root, selector) {
  const element = root.querySelector(selector);
  return element ? element.textContent.trim() : "";
}

try {
  globalThis.document = new FakeDocument();
  globalThis.HTMLElement = FakeElement;

  const modulePath = path.join(bundleRoot, "candidate", "workspace", "src", "app.mjs");
  const { mountBoard } = await import(pathToFileURL(modulePath));
  const items = [
    { id: "AUTH-HIDDEN-7", title: "Auth rollout", status: "blocked", owner: "Auth" },
    { id: "BILL-HIDDEN-4", title: "Billing ledger", status: "ready", owner: "Billing" },
    { id: "RISK-HIDDEN-9", title: "Risk review", status: "ready", owner: "Risk" }
  ];
  const originalItems = JSON.stringify(items);
  const root = document.createElement("div");
  mountBoard(root, items);

  assertCondition(textOf(root, "[data-summary]") === "3 / 3 visible", "runtime-initial-summary", "initial summary must show all cards");
  assertCondition(textOf(root, "[data-status]") === "No unsaved changes", "runtime-initial-status", "initial status text mismatch");

  const blocked = root.querySelector('[data-filter="blocked"]');
  assertCondition(Boolean(blocked), "runtime-filter-button", "blocked filter button missing");
  if (blocked) {
    click(blocked);
  }
  assertCondition(textOf(root, "[data-summary]") === "1 / 3 visible", "runtime-filter-summary", "blocked filter summary mismatch");
  assertCondition(root.querySelector('[data-filter="blocked"]')?.getAttribute("aria-pressed") === "true", "runtime-filter-pressed", "blocked filter aria-pressed not true");
  assertCondition(root.querySelector('[data-card-id="AUTH-HIDDEN-7"]')?.getAttribute("data-visible") === "true", "runtime-filter-visible-card", "blocked card not visible");
  assertCondition(root.querySelector('[data-card-id="BILL-HIDDEN-4"]')?.getAttribute("data-visible") === "false", "runtime-filter-hidden-card", "ready card not hidden under blocked filter");

  const dirtyToggle = root.querySelector('[data-card-id="AUTH-HIDDEN-7"] [data-dirty-toggle]');
  assertCondition(Boolean(dirtyToggle), "runtime-dirty-toggle", "dirty toggle missing");
  if (dirtyToggle) {
    keydown(dirtyToggle, " ");
  }
  assertCondition(root.querySelector('[data-card-id="AUTH-HIDDEN-7"]')?.getAttribute("data-dirty") === "true", "runtime-keyboard-dirty", "Space key did not mark card dirty");
  assertCondition(root.querySelector("[data-save]")?.hasAttribute("disabled") === false, "runtime-save-enabled", "save button still disabled after dirty toggle");
  assertCondition(textOf(root, "[data-status]") === "1 unsaved change", "runtime-dirty-status", "dirty status text mismatch");

  const save = root.querySelector("[data-save]");
  if (save) {
    click(save);
  }
  assertCondition(root.querySelector('[data-card-id="AUTH-HIDDEN-7"]')?.getAttribute("data-dirty") === "false", "runtime-save-clears-dirty", "save did not clear dirty marker");
  assertCondition(root.querySelector("[data-save]")?.hasAttribute("disabled") === true, "runtime-save-disabled", "save button not disabled after save");
  assertCondition(textOf(root, "[data-status]") === "All changes saved", "runtime-save-status", "save status text mismatch");

  assertCondition(JSON.stringify(items) === originalItems, "runtime-payload-immutability", "source item data was mutated");
} catch (error) {
  fail("runtime-exception", `${error.name}: ${error.message}`);
}

const payload = {
  verdict: failures.length === 0 ? "PASS" : "FAIL",
  failure_ids: failures.map((failure) => failure.id),
  failures
};
writeFileSync(metricsPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

if (failures.length > 0) {
  for (const failure of failures) {
    console.error(`Failed invariant: ${failure.id} :: ${failure.detail}`);
  }
  process.exit(1);
}

console.log("N73 DOM runtime PASS");
