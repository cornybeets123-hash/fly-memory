const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const source = readFileSync(join(__dirname, "../static/app.js"), "utf8");

function workshop(offline) {
  const elements = new Map();
  function element() {
    const children = new Map();
    return {
      style: {},
      classList: { toggle() {} },
      value: "2000",
      setAttribute() {},
      append() {},
      replaceChildren() {},
      querySelectorAll: () => [],
      querySelector(selector) {
        if (!children.has(selector)) children.set(selector, element());
        return children.get(selector);
      },
      getBoundingClientRect: () => ({ width: 800, height: 400 }),
      getContext: () => ({ setTransform() {}, clearRect() {}, fillRect() {} }),
    };
  }
  const runs = ["none", "personal", "shared"].map((mode) => {
    const event = {
      tick: 9,
      fly: 4,
      hits: [],
      vector: [],
      neural: {
        feeding: true,
        bitter_hz: 0,
        readouts_hz: { MN9: [86] },
        trial_id: "trial",
      },
    };
    return {
      mode,
      config: { flies: 12, steps: 600, epoch_steps: 100, wave: 350 },
      events: [event],
      chapters: [{ event, title: "An injury becomes experience", text: "" }],
      neural_trials: { trial: {} },
      frames: [{ tick: 0, flies: [[0, 0, 0, 100, 0, true, 0]] }],
    };
  });
  const context = vm.createContext({
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, element());
        return elements.get(id);
      },
      createElement: element,
      querySelectorAll: () => [],
      querySelector: () => null,
      addEventListener() {},
    },
    window: {
      ...(offline ? { WORKSHOP_DATA: { runs, probes: {} } } : {}),
      addEventListener() {},
    },
    fetch: async (path, options) => ({
      ok: true,
      json: async () => {
        if (path === "/api/status") return { code: "Completed code" };
        const { mode } = JSON.parse(options.body);
        return { runs: runs.filter((run) => run.mode === mode), code: "Completed code" };
      },
    }),
    matchMedia: () => ({ matches: false }),
    devicePixelRatio: 1,
    performance: { now: () => 1000 },
    // Hold animation frames still. Controls must recover without a clock change.
    requestAnimationFrame() {},
  });
  vm.runInContext(source, context);
  return { context, elements };
}

for (const offline of [false, true]) {
  for (const mode of ["none", "personal", "shared"]) {
    test(`${offline ? "offline" : "live"} ${mode}: repeated runs restore story controls`, async () => {
      const { context, elements } = workshop(offline);
      await new Promise(setImmediate);
      vm.runInContext(`setStage("${mode}")`, context);
      for (let attempt = 0; attempt < 3; attempt++) {
        await elements.get("run").onclick();
        assert.equal(elements.get("run").disabled, false);
        assert.equal(elements.get("next").disabled, false);
        assert.equal(elements.get("view").disabled, false);
        assert.equal(elements.get("decision").textContent, "?");
        elements.get("next").onclick();
        assert.equal(elements.get("decision").textContent, "Feeds");
      }
    });
  }
}
