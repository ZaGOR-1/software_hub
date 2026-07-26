"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const storage = new Map();
const localStorage = {
  getItem(key) {
    return storage.has(key) ? storage.get(key) : null;
  },
  setItem(key, value) {
    storage.set(key, String(value));
  },
  removeItem(key) {
    storage.delete(key);
  },
};

const rootAttributes = new Map();
const documentElement = {
  setAttribute(name, value) {
    rootAttributes.set(name, String(value));
  },
  removeAttribute(name) {
    rootAttributes.delete(name);
  },
};

const label = { textContent: "" };
const icon = { textContent: "" };
let clickHandler = null;
const buttonAttributes = new Map();
const button = {
  hidden: true,
  setAttribute(name, value) {
    buttonAttributes.set(name, String(value));
  },
  querySelector(selector) {
    if (selector === "[data-theme-label]") return label;
    if (selector === "[data-theme-icon]") return icon;
    return null;
  },
  addEventListener(name, handler) {
    if (name === "click") clickHandler = handler;
  },
};

let storageHandler = null;
const context = {
  console,
  document: {
    readyState: "complete",
    documentElement,
    querySelectorAll(selector) {
      return selector === "[data-theme-toggle]" ? [button] : [];
    },
    addEventListener() {},
  },
  window: {
    localStorage,
    addEventListener(name, handler) {
      if (name === "storage") storageHandler = handler;
    },
  },
};

const themeSource = fs.readFileSync("app/static/js/theme.js", "utf8");
vm.runInNewContext(themeSource, context, { filename: "theme.js" });

assert.equal(button.hidden, false);
assert.equal(label.textContent, "Системна тема");
assert.equal(rootAttributes.get("data-theme-preference"), "system");
assert.equal(rootAttributes.has("data-theme"), false);
assert.ok(clickHandler);

clickHandler();
assert.equal(storage.get("software-hub-theme"), "light");
assert.equal(rootAttributes.get("data-theme"), "light");
assert.equal(label.textContent, "Світла тема");

clickHandler();
assert.equal(storage.get("software-hub-theme"), "dark");
assert.equal(rootAttributes.get("data-theme"), "dark");
assert.equal(label.textContent, "Темна тема");

clickHandler();
assert.equal(storage.has("software-hub-theme"), false);
assert.equal(rootAttributes.has("data-theme"), false);
assert.equal(label.textContent, "Системна тема");

storage.set("software-hub-theme", "dark");
storageHandler({ key: "software-hub-theme" });
assert.equal(rootAttributes.get("data-theme"), "dark");

const bootstrapAttributes = new Map();
const bootstrapContext = {
  document: {
    documentElement: {
      setAttribute(name, value) {
        bootstrapAttributes.set(name, String(value));
      },
    },
  },
  window: {
    localStorage,
  },
};
const bootstrapSource = fs.readFileSync(
  "app/static/js/theme-bootstrap.js",
  "utf8",
);
vm.runInNewContext(bootstrapSource, bootstrapContext, {
  filename: "theme-bootstrap.js",
});
assert.equal(bootstrapAttributes.get("data-theme"), "dark");
assert.equal(bootstrapAttributes.get("data-theme-preference"), "dark");

console.log("Phase 14 theme runtime checks passed.");
