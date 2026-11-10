"use strict";
const $ = (id) => document.getElementById(id),
  reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const colors = {
  mint: "#8ce5c0",
  pink: "#ff4775",
  purple: "#b69aff",
  gold: "#f2c876",
  muted: "#a8b6c9",
};
const names = {
  none: "No memory",
  personal: "Personal memory",
  shared: "Shared memory",
};
const titles = {
  none: ["THE FIRST ENCOUNTER", "Can they survive?"],
  personal: ["YOUR FIRST BUILD", "Experience changes a decision."],
  shared: ["YOUR SECOND BUILD", "One fly learns. Others benefit."],
};
let stage = "none",
  runs = [],
  moments = [],
  momentIndex = 0,
  revealed = false,
  view = "encounter",
  tick = 0,
  playing = false,
  busy = false,
  lastTime = 0,
  sourceLabel = "Your code",
  probeResult = null;
let neuralStartedAt = 0;
let selectedRun = 0,
  selectedFly = 0,
  manualEvent = null;
const worlds = [];
async function api(path, body) {
  const r = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const d = await r.json();
  if (!r.ok)
    throw Error(
      typeof d.detail === "string" ? d.detail : "The experiment could not run.",
    );
  return d;
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function eventPoint(run, e) {
  return e.tick * run.config.flies + e.fly + 1;
}
function findSource(run, hit) {
  return hit ? run.events.find((e) => eventPoint(run, e) === hit.id) : null;
}
function bestHit(e) {
  return e?.hits
    .filter((h) => h.outcome === -1)
    .sort((a, b) => b.score - a.score)[0];
}
function narrative(run) {
  return run.chapters;
}

function current() {
  return manualEvent || moments[momentIndex]?.event || null;
}
function activeRun() {
  return runs[selectedRun] || runs.at(-1);
}
function setStage(value) {
  stage = value;
  document.querySelectorAll("[data-stage]").forEach((b) => {
    b.classList.toggle("active", b.dataset.stage === value);
    b.setAttribute("aria-pressed", String(b.dataset.stage === value));
  });
  [$("chapter").textContent, $("title").textContent] = titles[value];
  runs = [];
  moments = [];
  momentIndex = 0;
  tick = 0;
  playing = false;
  revealed = false;
  manualEvent = null;
  probeResult = null;
  view = "encounter";
  $("run").textContent = `Run ${names[value].toLowerCase()} ↗`;
  $("next").disabled = true;
  error("");
  buildWorlds();
  render();
}
document.querySelectorAll("[data-stage]").forEach(
  (b) =>
    (b.onclick = () => {
      if (!busy) setStage(b.dataset.stage);
    }),
);
async function run() {
  if (busy) return;
  busy = true;
  playing = false;
  error("");
  $("run").disabled = true;
  $("run").textContent = "Running…";
  render();
  try {
    let data;
    if (window.WORKSHOP_DATA) {
      const modes =
        stage === "none"
          ? ["none"]
          : stage === "personal"
            ? ["none", "personal"]
            : ["personal", "shared"];
      data = {
        runs: modes.map((m) =>
          window.WORKSHOP_DATA.runs.find((r) => r.mode === m),
        ),
        code: "Offline replay",
      };
    } else
      data = await api("/api/run", {
        mode: stage,
        seed: Number($("seed").value),
      });
    runs = data.runs;
    sourceLabel = data.code;
    selectedRun = runs.length - 1;
    moments = narrative(activeRun());
    momentIndex = 0;
    manualEvent = null;
    revealed = false;
    probeResult = null;
    view = "encounter";
    tick = current()?.tick || 0;
    selectedFly = current()?.fly || 0;
    $("timeline").max = runs[0].config.steps - 1;
    $("code-label").textContent = sourceLabel;
    buildWorlds();
  } catch (e) {
    error(e.message + " Open Build memory for this task.");
  } finally {
    busy = false;
    $("run").disabled = false;
    $("run").textContent = "Run again ↗";
    render();
  }
}
$("run").onclick = run;
function showView(value) {
  if (busy) return;
  view = value;
  playing = false;
  render();
}
$("view").onclick = () =>
  showView(view === "encounter" ? "colony" : "encounter");
$("next").onclick = () => {
  if (!runs.length || busy) return;
  if (view === "colony") {
    view = "encounter";
    selectedRun = runs.length - 1;
    moments = narrative(activeRun());
    momentIndex = 0;
    manualEvent = null;
    revealed = false;
    probeResult = null;
    tick = current()?.tick || 0;
  } else if (!revealed) {
    revealed = true;
    neuralStartedAt = performance.now() / 1000;
    tick = current()?.tick || 0;
  } else if (momentIndex < moments.length - 1 && !manualEvent) {
    momentIndex++;
    revealed = false;
    probeResult = null;
    tick = current().tick;
  } else {
    view = "colony";
    tick = 0;
    playing = !reduced;
    probeResult = null;
  }
  render();
};
function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect(),
    dpr = Math.min(devicePixelRatio || 1, 2);
  const w = rect.width,
    h = rect.height;
  if (
    canvas.width !== Math.round(w * dpr) ||
    canvas.height !== Math.round(h * dpr)
  ) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const g = canvas.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  return { g, w, h };
}
function circle(g, x, y, r, fill, stroke) {
  g.beginPath();
  g.arc(x, y, r, 0, Math.PI * 2);
  if (fill) {
    g.fillStyle = fill;
    g.fill();
  }
  if (stroke) {
    g.strokeStyle = stroke;
    g.stroke();
  }
}
function fruit(g, x, y, family, size = 1, hazard = false) {
  g.save();
  g.translate(x, y);
  g.scale(size, size);
  const color = hazard ? colors.pink : colors.mint;
  g.shadowColor = color;
  g.shadowBlur = hazard ? 17 : 10;
  circle(g, 0, 0, 32, "#142739", color);
  g.shadowBlur = 0;
  if (hazard) {
    g.lineWidth = 3;
    circle(g, 0, 0, 37, null, color);
    g.save();
    g.beginPath();
    g.arc(0, 0, 30, 0, Math.PI * 2);
    g.clip();
    g.strokeStyle = "#ff47752b";
    g.lineWidth = 3;
    for (let n = -60; n < 60; n += 10) {
      g.beginPath();
      g.moveTo(n, -40);
      g.lineTo(n + 80, 40);
      g.stroke();
    }
    g.restore();
  }
  if (family === 0) {
    g.beginPath();
    g.moveTo(-15, -12);
    g.bezierCurveTo(-11, 18, 12, 23, 23, -4);
    g.bezierCurveTo(5, 11, -2, 4, -7, -16);
    g.closePath();
    g.fillStyle = "#f7ce5f";
    g.fill();
    g.beginPath();
    g.moveTo(-9, -12);
    g.lineTo(-13, -19);
    g.lineWidth = 4;
    g.strokeStyle = "#9f7c42";
    g.stroke();
  } else if (family === 1) {
    g.beginPath();
    g.moveTo(-4, -17);
    g.bezierCurveTo(-9, -16, -8, -5, -16, 4);
    g.bezierCurveTo(-27, 27, 27, 27, 16, 4);
    g.bezierCurveTo(8, -5, 9, -16, 4, -17);
    g.closePath();
    g.fillStyle = "#bdd66f";
    g.fill();
    g.beginPath();
    g.moveTo(0, -15);
    g.lineTo(4, -25);
    g.lineWidth = 3;
    g.strokeStyle = "#b4c28a";
    g.stroke();
  } else {
    [
      [-12, 4],
      [0, 14],
      [13, 1],
      [0, -10],
    ].forEach(([a, b], i) =>
      circle(g, a, b, 9, ["#c28dea", "#ab70ce", "#bd82e2", "#d7a3f2"][i]),
    );
    g.beginPath();
    g.moveTo(0, -18);
    g.lineTo(6, -28);
    g.lineWidth = 3;
    g.strokeStyle = "#a7c08f";
    g.stroke();
  }
  if (hazard) {
    g.beginPath();
    g.moveTo(22, -40);
    g.lineTo(34, -18);
    g.lineTo(10, -18);
    g.closePath();
    g.fillStyle = colors.pink;
    g.fill();
    g.fillStyle = "#0c111c";
    g.font = "900 15px Arial";
    g.textAlign = "center";
    g.fillText("!", 22, -22);
  }
  g.restore();
}
function fly(
  g,
  x,
  y,
  size,
  angle,
  phase,
  injuries = 0,
  dead = false,
  selected = false,
) {
  g.save();
  g.translate(x, y);
  if (selected) {
    g.lineWidth = 2;
    circle(g, 0, 0, size * 1.5, null, colors.purple);
  }
  g.shadowColor = dead ? colors.pink : colors.mint;
  g.shadowBlur = dead ? 0 : 10;
  drawSpecimen(g, size, angle, phase, dead ? "#bb7a8b" : "#90e5c2", false);
  g.shadowBlur = 0;
  if (dead) {
    g.strokeStyle = colors.pink;
    g.lineWidth = 3;
    g.beginPath();
    g.moveTo(-size * 0.6, -size * 0.6);
    g.lineTo(size * 0.6, size * 0.6);
    g.moveTo(size * 0.6, -size * 0.6);
    g.lineTo(-size * 0.6, size * 0.6);
    g.stroke();
  }
  g.restore();
  for (let n = 0; n < 3; n++) {
    const xx = x + (n - 1) * size * 0.45,
      yy = y + size * 1.7;
    circle(
      g,
      xx,
      yy,
      Math.max(3, size * 0.09),
      n < injuries ? colors.pink : "#ffffff20",
    );
  }
}
function drawEncounter(now) {
  if (view !== "encounter") return;
  const { g, w, h } = setupCanvas($("encounter-canvas")),
    e = current(),
    run = activeRun();
  const node = e
    ? run.nodes[Math.floor(e.tick / run.config.epoch_steps)].find(
        (n) => n.id === e.object,
      )
    : { family: 0, hazard: true };
  const x1 = w * 0.29,
    x2 = w * 0.72,
    y = h * 0.43;
  const inj = e
      ? run.events.filter(
          (previous) =>
            previous.fly === e.fly &&
            previous.tick < e.tick &&
            previous.outcome === -1,
        ).length
      : 0,
    after = revealed && e,
    refuses = after && !(probeResult?.neural || e.neural).feeding;
  g.strokeStyle = "#ffffff08";
  g.lineWidth = 1;
  for (let i = 1; i < 9; i++) {
    g.beginPath();
    g.moveTo((i * w) / 9, 0);
    g.lineTo((i * w) / 9, h);
    g.stroke();
  }
  for (let i = 1; i < 6; i++) {
    g.beginPath();
    g.moveTo(0, (i * h) / 6);
    g.lineTo(w, (i * h) / 6);
    g.stroke();
  }
  if (after && e.outcome === -1 && !probeResult) {
    g.fillStyle = "#ff47750e";
    g.fillRect(0, 0, w, h);
  }
  // Odor waves explain the input; they do not represent neural spike trains.
  g.strokeStyle = "#b69aff65";
  g.lineWidth = 2;
  for (let i = 0; i < 3; i++) {
    const offset = reduced ? i * 20 : (now * 18 + i * 24) % 85;
    g.beginPath();
    g.arc(x2, y, 55 + offset, Math.PI * 0.8, Math.PI * 1.2);
    g.stroke();
  }
  fruit(g, x2, y, node.family, Math.min(w / 430, 1.9), node.hazard);
  fly(
    g,
    x1 - (refuses ? 25 : 0),
    y,
    Math.min(w / 8, 78),
    refuses ? Math.PI : 0,
    reduced ? 0 : now * 3,
    inj + (after && e.outcome === -1 && !probeResult ? 1 : 0),
    false,
    true,
  );
  g.font = "600 17px Mona,Arial";
  g.fillStyle = colors.muted;
  g.textAlign = "center";
  g.fillText(
    e ? `Fly ${String(e.fly + 1).padStart(2, "0")}` : "Fly 05",
    x1,
    y - 105,
  );
  g.fillStyle = node.hazard ? colors.pink : colors.mint;
  g.fillText(node.hazard ? "POISON" : "FOOD", x2, y + 94);
  if (after) {
    const result = probeResult?.neural || e.neural;
    g.fillStyle = result.feeding
      ? node.hazard
        ? colors.pink
        : colors.mint
      : colors.purple;
    g.font = "650 27px Mona,Arial";
    g.fillText(
      probeResult
        ? result.feeding
          ? "WOULD FEED"
          : "WOULD REFUSE"
        : result.feeding
          ? node.hazard
            ? "INJURED"
            : "FED"
          : "REFUSES",
      w * 0.5,
      h * 0.7,
    );
    if (!probeResult && e.outcome !== null) {
      g.font = "15px Mona,Arial";
      g.fillStyle = colors.muted;
      g.fillText(
        run.mode === "none"
          ? "No experience is saved."
          : `Observation #${eventPoint(run, e)} is saved.`,
        w * 0.5,
        h * 0.77,
      );
    }
  }
}
function drawOdor() {
  const { g, w, h } = setupCanvas($("odor-canvas")),
    vector = current()?.vector || [];
  const n = vector.length || 24;
  for (let i = 0; i < n; i++) {
    const v = Math.abs(vector[i] || 0),
      bar = Math.max(2, Math.min(h - 7, v * 120));
    g.fillStyle = vector[i] >= 0 ? colors.purple : "#5f648f";
    g.fillRect((i * w) / n, h - bar, w / n - 3, bar);
  }
}
function drawNeural(now) {
  if (view !== "encounter") return;
  const { g, w, h } = setupCanvas($("neural-canvas")),
    e = current();
  if (!e || !revealed) {
    g.fillStyle = "#ffffff12";
    g.fillRect(0, h / 2, w, 1);
    return;
  }
  const neural = probeResult?.neural || e.neural,
    run = activeRun(),
    traces = run.neural_trials[neural.trial_id],
    cursor = reduced ? 1 : Math.max(0, (now - neuralStartedAt) / 6) % 1;
  const rows = [
      ["sugar", "Sugar input", colors.gold],
      ["bitter", "Bitter input", colors.purple],
      ["motor", "MN9 left", neural.feeding ? colors.mint : colors.pink],
    ],
    left = 115,
    right = w - 5;
  rows.forEach(([key, label, color], i) => {
    const y = 16 + i * 30;
    g.font = "16px Mona,Arial";
    g.fillStyle = colors.muted;
    g.textAlign = "left";
    g.fillText(label, 0, y + 3);
    g.strokeStyle = "#ffffff19";
    g.beginPath();
    g.moveTo(left, y);
    g.lineTo(right, y);
    g.stroke();
    g.strokeStyle = color;
    g.lineWidth = 1;
    for (const t of traces?.[key] || []) {
      const x = left + t * (right - left);
      g.globalAlpha = reduced || t <= cursor ? 1 : 0.2;
      g.beginPath();
      g.moveTo(x, y - 7);
      g.lineTo(x, y + 7);
      g.stroke();
    }
    g.globalAlpha = 1;
    const active = (traces?.[key] || []).some(
      (t) => t <= cursor && cursor - t < 0.025,
    );
    circle(g, left - 10, y, 4, active ? color : "#ffffff20");
  });
  if (!reduced) {
    g.strokeStyle = "#ffffff55";
    const x = left + cursor * (right - left);
    g.beginPath();
    g.moveTo(x, 3);
    g.lineTo(x, h - 2);
    g.stroke();
  }
}
function render() {
  $("encounter").hidden = view !== "encounter";
  $("colony").hidden = view !== "colony";
  $("view").textContent =
    view === "encounter" ? "Show colony ↗" : "Follow the story ↗";
  const e = current(),
    run = activeRun(),
    moment = manualEvent ? null : moments[momentIndex];
  $("scene-title").textContent = manualEvent
    ? "Inspect this contact."
    : !revealed && e
      ? "Will the fly eat?"
      : moment?.title || "A sweet scent can hide danger.";
  $("scene-position").textContent = e
    ? `FLY ${String(e.fly + 1).padStart(2, "0")} · CONTACT ${e.tick} · ENLARGED`
    : "ONE FLY. ONE DECISION.";
  $("sense-title").textContent = "The fly senses an odor.";
  const hit = e ? bestHit(probeResult || e) : null,
    source = findSource(run || { events: [] }, hit);
  $("memory-title").textContent = hit
    ? hit.source_fly === e.fly
      ? "Its own experience"
      : "Another fly's experience"
    : "No stored warning";
  $("memory-detail").textContent = source
    ? `Fly ${String(source.fly + 1).padStart(2, "0")} ate ${source.outcome === -1 ? "poisoned food" : "safe food"} at step ${source.tick}.`
    : e
      ? "No similar harmful observation was retrieved."
      : "The next meal will reveal its outcome.";
  $("memory-match").hidden = !hit;
  $("memory-source").textContent = hit ? `Stored observation #${hit.id}` : "";
  $("memory-score").textContent = hit
    ? `${hit.score.toFixed(3)} similarity`
    : "";
  $("ablate").hidden =
    !e ||
    !revealed ||
    !bestHit(e) ||
    Boolean(
      window.WORKSHOP_DATA &&
        !window.WORKSHOP_DATA.probes[`${run.mode}:${e.tick}:${e.fly}`],
    );
  $("ablate").disabled = busy;
  $("next").disabled = busy || !runs.length;
  $("view").disabled = busy;
  $("ablate").textContent = probeResult
    ? "Restore memory ↗"
    : "Remove this memory and requery ↗";
  const neural = probeResult?.neural || e?.neural;
  $("decision").textContent = !revealed
    ? "?"
    : neural?.feeding
      ? probeResult
        ? "Would feed"
        : "Feeds"
      : probeResult
        ? "Would refuse"
        : "Refuses";
  $("decision").style.color = !revealed
    ? "#f0f3fa"
    : neural?.feeding
      ? colors.pink
      : colors.mint;
  $("motor-rate").textContent = !revealed
    ? "Predict the decision."
    : `${neural.readouts_hz.MN9[0]} Hz motor · bitter input ${neural.bitter_hz} Hz · gate >10 Hz`;
  $("neural-label").textContent = resemblesUnavailable()
    ? "Neural replay unavailable."
    : "Recorded 1 s trial, 6× slower. Inputs: 1 of 21 each. Output: MN9 left.";
  $("next").textContent =
    view === "colony"
      ? "Replay the story ↗"
      : !revealed
        ? "Reveal decision ↗"
        : momentIndex < moments.length - 1 && !manualEvent
          ? "Next encounter ↗"
          : "Watch the colony ↗";
  $("story-count").textContent =
    view === "colony"
      ? "COLONY"
      : manualEvent
        ? "INSPECT"
        : runs.length
          ? `${momentIndex + 1} / ${moments.length}`
          : "START HERE";
  $("story-text").textContent = probeResult
    ? `Memory removed. Decision replay only. No outcome is written; the colony stays unchanged.`
    : view === "colony"
      ? "Each colony starts empty. The world and neural seeds stay fixed."
      : manualEvent
        ? "Inspect this contact's retrieved evidence and feeding response."
        : moment?.text ||
          "Twelve flies must eat. Three poisoned meals kill a fly.";
  $("verify").disabled = !revealed || !e || Boolean(window.WORKSHOP_DATA);
  $("play").textContent = playing ? "Ⅱ" : "▶";
  $("play").setAttribute(
    "aria-label",
    playing ? "Pause experiment" : "Play experiment",
  );
  $("timeline").value = Math.floor(tick);
  $("time").textContent = runs.length
    ? `Round ${Math.floor(tick / runs[0].config.epoch_steps) + 1} / ${Math.ceil(runs[0].config.steps / runs[0].config.epoch_steps)}`
    : "0%";
  $("wave").hidden = !(
    view === "colony" &&
    runs.length &&
    tick >= runs[0].config.wave &&
    tick < runs[0].config.wave + 35
  );
  worlds.forEach((world) => {
    if (!world.run) return;
    const frame = stateAt(world.run),
      alive = frame.flies.filter((f) => f[5]).length;
    world.section.querySelector(".alive b").textContent = alive;
    world.section.querySelector(".meals strong").textContent =
      frame.flies.reduce((s, f) => s + f[6], 0);
    world.section.querySelector(".injuries strong").textContent =
      frame.flies.reduce((s, f) => s + f[4], 0);
    world.section.querySelectorAll(".roster>span").forEach((el, i) => {
      const f = frame.flies[i];
      el.querySelector("i").className = !f[5] ? "dead" : f[4] ? "hurt" : "";
      el.querySelector("em").textContent = "●".repeat(f[4]);
    });
  });
  drawOdor();
}
function resemblesUnavailable() {
  const e = current();
  return (
    revealed &&
    e &&
    !activeRun()?.neural_trials?.[(probeResult?.neural || e.neural).trial_id]
  );
}
$("ablate").onclick = async () => {
  if (busy) return;
  if (probeResult) {
    probeResult = null;
    neuralStartedAt = performance.now() / 1000;
    render();
    return;
  }
  const e = current(),
    run = activeRun(),
    hit = bestHit(e);
  if (!hit) return;
  busy = true;
  error("");
  render();
  try {
    if (window.WORKSHOP_DATA) {
      probeResult =
        window.WORKSHOP_DATA.probes[`${run.mode}:${e.tick}:${e.fly}`];
      if (!probeResult)
        throw Error("This checkpoint requires the live workshop.");
    } else
      probeResult = await api("/api/probe", {
        mode: run.mode,
        seed: run.config.seed,
        tick: e.tick,
        fly: e.fly,
        exclude_ids: [hit.id],
      });
  } catch (e) {
    error(e.message);
  } finally {
    busy = false;
    neuralStartedAt = performance.now() / 1000;
    render();
  }
};
function buildWorlds() {
  $("habitats").replaceChildren();
  worlds.length = 0;
  $("habitats").classList.toggle("compare", runs.length > 1);
  runs.forEach((run, index) => {
    const section = document.createElement("section");
    section.className = "habitat";
    section.innerHTML = `<div class="world-heading"><h2>${names[run.mode]}</h2><div class="alive"><b>12</b><small>/ 12 alive</small></div></div><div class="dish"><canvas role="img" aria-label="Fly colony with audience-visible food and poison markings. Select a fly to inspect."></canvas></div><div class="roster">${Array.from({ length: run.config.flies }, (_, i) => `<span><i></i>${String(i + 1).padStart(2, "0")}<em></em></span>`).join("")}</div><div class="world-stats"><span class="meals"><strong>0</strong>safe meals</span><span class="injuries"><strong>0</strong>injuries</span></div>`;
    $("habitats").append(section);
    const canvas = section.querySelector("canvas");
    const world = { section, canvas, run, index };
    worlds.push(world);
    canvas.onclick = (event) => {
      if (busy) return;
      const rect = canvas.getBoundingClientRect(),
        x = ((event.clientX - rect.left) / rect.width) * run.config.width,
        y = ((event.clientY - rect.top) / rect.height) * run.config.height;
      const frame = stateAt(run),
        nearest = frame.flies
          .map((f, i) => [Math.hypot(f[0] - x, f[1] - y), i])
          .sort((a, b) => a[0] - b[0])[0];
      selectedRun = index;
      selectedFly = nearest[1];
      manualEvent =
        run.events
          .filter((e) => e.fly === selectedFly && e.tick <= tick)
          .at(-1) || run.events.find((e) => e.fly === selectedFly);
      if (manualEvent) {
        tick = manualEvent.tick;
        revealed = true;
        probeResult = null;
        showView("encounter");
      }
    };
  });
}
function stateAt(run) {
  return run.frames.findLast((frame) => frame.tick <= tick) || run.frames[0];
}
function drawWorld(world, now) {
  const { g, w, h } = setupCanvas(world.canvas),
    run = world.run,
    s = w / run.config.width;
  g.fillStyle = "#112031";
  g.fillRect(0, 0, w, h);
  g.strokeStyle = "#ffffff08";
  g.lineWidth = 1;
  for (let i = 8; i < 64; i += 8) {
    g.beginPath();
    g.moveTo(i * s, 0);
    g.lineTo(i * s, h);
    g.stroke();
  }
  for (let i = 6; i < 38; i += 6) {
    g.beginPath();
    g.moveTo(0, i * s);
    g.lineTo(w, i * s);
    g.stroke();
  }
  const epoch = Math.min(
    run.nodes.length - 1,
    Math.floor(tick / run.config.epoch_steps),
  );
  run.nodes[epoch].forEach((n) =>
    fruit(
      g,
      n.x * s,
      n.y * s,
      n.family,
      Math.max(0.42, Math.min(0.85, s / 11)),
      n.hazard,
    ),
  );
  const frame = stateAt(run);
  frame.flies.forEach((f, i) => {
    const [baseX, baseY, baseAngle, energy, injury, alive] = f;
    const next =
      run.frames[Math.min(run.frames.length - 1, Math.floor(tick / 2) + 1)];
    const nextFly = next.flies[i];
    const blend =
      playing && alive && nextFly[5] && next.tick > frame.tick
        ? Math.min(
            1,
            Math.max(0, (tick - frame.tick) / (next.tick - frame.tick)),
          )
        : 0;
    const x = baseX + (nextFly[0] - baseX) * blend;
    const y = baseY + (nextFly[1] - baseY) * blend;
    const turn =
      ((nextFly[2] - baseAngle + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
    const a = baseAngle + turn * blend;
    fly(
      g,
      x * s,
      y * s,
      Math.max(13, Math.min(25, s * 1.9)),
      a,
      playing ? now * 6 + i : 0,
      injury,
      !alive,
      false,
    );
  });
  const recent = run.events.filter((e) => e.tick <= tick && tick - e.tick < 20);
  recent.forEach((e) => {
    if (e.action === "hurt" || e.action === "dead") {
      g.lineWidth = 3;
      circle(g, e.position[0] * s, e.position[1] * s, 28, null, colors.pink);
    } else if (e.shared_changed_decision) {
      g.lineWidth = 3;
      circle(g, e.position[0] * s, e.position[1] * s, 28, null, colors.purple);
    }
  });
}
$("play").onclick = () => {
  if (!runs.length) return;
  if (tick >= runs[0].config.steps - 1) tick = 0;
  playing = !playing;
  render();
};
$("timeline").oninput = () => {
  playing = false;
  tick = Number($("timeline").value);
  render();
};
$("inspect").onclick = () => {
  const run = runs.at(-1);
  if (!run) return;
  selectedRun = runs.length - 1;
  manualEvent =
    run.events.filter((e) => e.tick <= tick).at(-1) || run.events[0];
  if (manualEvent) {
    tick = manualEvent.tick;
    revealed = true;
    probeResult = null;
    showView("encounter");
  }
};
$("help").onclick = async () => {
  try {
    const s = stage === "shared" ? "shared" : "personal",
      lesson =
        window.WORKSHOP_DATA?.lessons?.[s] || (await api(`/api/lesson/${s}`));
    $("lesson-file").textContent = lesson.file;
    $("lesson-instruction").textContent = lesson.instruction;
    $("lesson-check").textContent = lesson.check;
    $("lesson-code").textContent = lesson.code;
    $("lesson-dialog").showModal();
  } catch (e) {
    error(e.message);
  }
};
$("about").onclick = () => $("about-dialog").showModal();
document
  .querySelectorAll("dialog .close")
  .forEach((b) => (b.onclick = () => b.closest("dialog").close()));
async function fullscreen() {
  if (document.fullscreenElement) await document.exitFullscreen();
  else await document.documentElement.requestFullscreen();
}
document.addEventListener("fullscreenchange", () =>
  document.body.classList.toggle("room", Boolean(document.fullscreenElement)),
);
$("fullscreen").onclick = fullscreen;
$("verify").onclick = async () => {
  const e = current();
  if (!e) return;
  $("verify").disabled = true;
  $("verification").textContent = "Computing the original neural trial…";
  try {
    const n = probeResult?.neural || e.neural,
      r = await api("/api/verify", { bitter: n.bitter_hz, seed: n.seed });
    $("verification").textContent = r.matches_recording
      ? `Live computation matched: ${r.readouts_hz.MN9[0]} Hz.`
      : "Live computation differed. Inspect the recorded protocol.";
  } catch (e) {
    $("verification").textContent = e.message;
  } finally {
    $("verify").disabled = false;
  }
};
$("download-frame").onclick = () => {
  const out = document.createElement("canvas");
  out.width = 1920;
  out.height = 1080;
  const g = out.getContext("2d");
  g.fillStyle = "#0c111c";
  g.fillRect(0, 0, 1920, 1080);
  g.fillStyle = "#f0f3fa";
  g.font = "600 50px Mona,Arial";
  g.fillText($("title").textContent, 60, 85);
  if (view === "colony") {
    worlds.forEach((world, i) => {
      const count = worlds.length,
        width = (1800 - (count - 1) * 36) / count,
        x = 60 + i * (width + 36),
        height = (width * 38) / 64;
      g.font = "600 30px Mona,Arial";
      g.fillText(names[world.run.mode], x, 160);
      g.drawImage(world.canvas, x, 190, width, Math.min(height, 650));
      const frame = stateAt(world.run);
      g.font = "600 26px Mona,Arial";
      g.fillStyle = colors.mint;
      g.fillText(
        `${frame.flies.filter((f) => f[5]).length}/12 alive · ${frame.flies.reduce((s, f) => s + f[6], 0)} safe meals · ${frame.flies.reduce((s, f) => s + f[4], 0)} injuries`,
        x,
        230 + Math.min(height, 650),
      );
      g.fillStyle = "#f0f3fa";
    });
  } else {
    g.drawImage($("encounter-canvas"), 60, 150, 1120, 750);
    g.font = "600 28px Mona,Arial";
    let y = 230;
    for (const id of [
      "memory-title",
      "memory-detail",
      "memory-score",
      "decision",
      "motor-rate",
    ]) {
      const text = $(id).textContent;
      const words = text.split(" ");
      let line = "";
      for (const word of words) {
        if (g.measureText(line + word).width > 550) {
          g.fillText(line, 1240, y);
          y += 40;
          line = "";
        }
        line += word + " ";
      }
      g.fillText(line, 1240, y);
      y += 70;
    }
    g.drawImage($("neural-canvas"), 1240, 700, 600, 170);
  }
  g.font = "20px Mona,Arial";
  g.fillStyle = colors.muted;
  g.fillText(
    "Audience view: hazards revealed. Computed neural replay. Engineered movement. Qdrant Edge retrieval.",
    60,
    1030,
  );
  const a = document.createElement("a");
  a.href = out.toDataURL("image/png");
  a.download = `fly-memory-${stage}.png`;
  a.click();
};
window.addEventListener("keydown", (e) => {
  if (
    e.target.matches("input,textarea,select") ||
    e.ctrlKey ||
    e.metaKey ||
    e.altKey ||
    document.querySelector("dialog[open]")
  )
    return;
  if (e.code === "Space") {
    e.preventDefault();
    $(view === "encounter" ? "next" : "play").click();
  } else if (["1", "2", "3"].includes(e.key) && !busy)
    setStage(["none", "personal", "shared"][Number(e.key) - 1]);
  else if (e.key.toLowerCase() === "f") fullscreen();
  else if (e.key.toLowerCase() === "v") $("view").click();
  else if (e.key.toLowerCase() === "r") run();
});
let renderKey = "";
function frame(now) {
  const dt = lastTime ? Math.min(0.1, (now - lastTime) / 1000) : 0;
  lastTime = now;
  if (playing && view === "colony" && runs.length) {
    tick += dt * Number($("speed").value);
    if (tick >= runs[0].config.steps - 1) {
      tick = runs[0].config.steps - 1;
      playing = false;
    }
  }
  if (view === "colony") worlds.forEach((w) => drawWorld(w, now / 1000));
  else {
    drawEncounter(now / 1000);
    drawNeural(now / 1000);
  }
  const key = `${Math.floor(tick / 2)}/${playing}`;
  if (key !== renderKey) {
    render();
    renderKey = key;
  }
  requestAnimationFrame(frame);
}
async function init() {
  try {
    const s = window.WORKSHOP_DATA
      ? { code: "Offline replay" }
      : await api("/api/status");
    sourceLabel = s.code;
    $("code-label").textContent = sourceLabel;
    if (window.WORKSHOP_DATA) {
      $("seed").value = window.WORKSHOP_DATA.runs[0].config.seed;
      $("seed").disabled = true;
    }
  } catch (e) {
    error(e.message);
  }
  render();
  requestAnimationFrame(frame);
}
init();
