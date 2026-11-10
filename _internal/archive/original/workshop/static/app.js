"use strict";
const $ = (id) => document.getElementById(id);
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const palette = {
  pink: "#f05b85",
  mint: "#a1dfc2",
  gold: "#e9bc72",
  blue: "#87aeea",
  muted: "#969bb3",
};
let mode = "balanced",
  result = null,
  bank = null,
  subject = 6,
  step = 0,
  clock = 0,
  playing = !reduced,
  busy = false,
  previous = 0,
  selectedPoint = null,
  interventionRequest = null,
  mapPoints = [];
const recordings = new Map();
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const label = (fly) => String(fly + 1).padStart(2, "0");
function config() {
  return {
    mode: $("control").value === "normal" ? mode : $("control").value,
    seed: Number($("seed").value),
    threshold: Number($("threshold").value),
    top_k: Number($("top-k").value),
    representation: $("representation").value,
    noise: Number($("noise").value),
    marker: Number($("marker").value),
    margin: Number($("margin").value),
  };
}
async function api(path, body) {
  const response = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function working(value, message = "Running experiment") {
  busy = value;
  for (const id of ["run", "benchmark", "verify", "surgery", "live-surgery"])
    $(id).disabled = value;
  $("experiment-state").textContent = message;
  $("run").textContent = value ? "Running…" : "Run experiment ↗";
  if (value) error("");
}
function setMode(value) {
  mode = value;
  document.querySelectorAll("[data-mode]").forEach((b) => {
    const selected = b.dataset.mode === value;
    b.classList.toggle("active", selected);
    b.setAttribute("aria-pressed", String(selected));
  });
  $("control").value = "normal";
  if (result)
    $("experiment-state").textContent = "Settings changed. Run experiment.";
}
for (const button of document.querySelectorAll("[data-mode]"))
  button.onclick = () => setMode(button.dataset.mode);
for (const id of ["threshold", "noise", "marker", "margin"]) {
  $(id).oninput = () => {
    $(id + "-label").textContent =
      id === "marker"
        ? Math.round(Number($(id).value) * 100) + "%"
        : Number($(id).value).toFixed(id === "noise" ? 3 : 2);
    if (result)
      $("experiment-state").textContent = "Settings changed. Run experiment.";
  };
}
for (const id of ["seed", "top-k", "representation", "control"])
  $(id).onchange = () => {
    $("experiment-state").textContent = "Settings changed. Run experiment.";
  };
async function run() {
  if (busy) return;
  working(true);
  try {
    result = await api("/api/run", config());
    step = 0;
    clock = 0;
    selectedPoint = null;
    subject = Math.min(subject, result.histories.length - 1);
    $("scrub").max = result.config.encounters - 1;
    playing = !reduced;
    $("experiment-state").textContent =
      `${result.config.mode.toUpperCase()} · SEED ${result.config.seed}`;
    render();
  } catch (e) {
    error(e.message);
  } finally {
    working(
      false,
      result
        ? `${result.config.mode.toUpperCase()} · SEED ${result.config.seed}`
        : "Experiment failed",
    );
  }
}
$("run").onclick = run;
function current() {
  if (!result) return null;
  const history = result.histories[subject];
  return history[Math.min(step, history.length - 1)];
}
function phase() {
  return result && step > current().step
    ? 3
    : Math.min(3, Math.floor(clock / 0.9));
}
function go(value) {
  if (!result) return;
  step = Math.max(0, Math.min(result.config.encounters - 1, value));
  clock = 0;
  selectedPoint = null;
  render();
}
$("play").onclick = () => {
  if (!result) return;
  playing = !playing;
  if (playing && step === result.config.encounters - 1 && clock >= 3.6) go(0);
  render();
};
$("next").onclick = () => {
  playing = false;
  go(step + 1);
  clock = 3.59;
  render();
};
$("previous").onclick = () => {
  playing = false;
  go(step - 1);
  clock = 3.59;
  render();
};
$("scrub").oninput = () => {
  playing = false;
  go(Number($("scrub").value));
  clock = 3.59;
  render();
};
function knownPoints(event) {
  if (!result || !event) return [];
  return result.memories[subject].filter(
    (p) => p.tick < event.step || (p.tick === event.step && phase() === 3),
  );
}
function fit(id) {
  const canvas = $(id),
    rect = canvas.getBoundingClientRect(),
    dpr = Math.min(devicePixelRatio || 1, 2);
  if (
    canvas.width !== Math.round(rect.width * dpr) ||
    canvas.height !== Math.round(rect.height * dpr)
  ) {
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
  }
  const g = canvas.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, rect.width, rect.height);
  return { g, w: rect.width, h: rect.height };
}
function text(
  g,
  value,
  x,
  y,
  size = 10,
  color = palette.muted,
  align = "left",
) {
  g.font = `${size}px Mona, sans-serif`;
  g.fillStyle = color;
  g.textAlign = align;
  g.textBaseline = "middle";
  g.fillText(value, x, y);
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
    g.lineWidth = 1;
    g.stroke();
  }
}
function line(g, points, color, width = 1) {
  if (!points.length) return;
  g.beginPath();
  g.moveTo(...points[0]);
  for (const p of points.slice(1)) g.lineTo(...p);
  g.strokeStyle = color;
  g.lineWidth = width;
  g.stroke();
}
function fruit(g, x, y, scale, family, observed) {
  g.save();
  g.translate(x, y);
  g.scale(scale, scale);
  g.shadowColor = "#5f462833";
  g.shadowBlur = 9;
  g.shadowOffsetY = 5;
  if (family === "banana") {
    g.fillStyle = "#dcaf4f";
    g.beginPath();
    g.moveTo(-17, -10);
    g.bezierCurveTo(-10, 15, 9, 20, 24, 0);
    g.bezierCurveTo(10, 32, -14, 28, -25, 0);
    g.closePath();
    g.fill();
    g.strokeStyle = "#9d763d";
    g.lineWidth = 1;
    g.stroke();
    g.shadowBlur = 0;
    line(
      g,
      [
        [-18, -5],
        [-8, 14],
        [9, 17],
        [21, 4],
      ],
      "#f4da8c",
      3,
    );
    line(
      g,
      [
        [-24, 0],
        [-27, -5],
      ],
      "#695138",
      3,
    );
  } else if (family === "pear") {
    g.fillStyle = "#98a55b";
    g.beginPath();
    g.moveTo(0, -20);
    g.bezierCurveTo(-12, -18, -6, -5, -17, 4);
    g.bezierCurveTo(-32, 30, 32, 30, 18, 3);
    g.bezierCurveTo(7, -6, 10, -21, 0, -20);
    g.fill();
    g.shadowBlur = 0;
    line(
      g,
      [
        [0, -20],
        [3, -30],
      ],
      "#715a39",
      3,
    );
    g.fillStyle = "#adbb69";
    g.beginPath();
    g.ellipse(10, -26, 9, 4, -0.4, 0, Math.PI * 2);
    g.fill();
    circle(g, -6, 8, 4, "#d8d79a55");
  } else {
    for (let i = 0; i < 3; i++)
      circle(
        g,
        (i - 1) * 15,
        (i % 2) * 8,
        13,
        ["#a06975", "#c28b69", "#a98958"][i],
      );
    g.shadowBlur = 0;
    for (let i = 0; i < 3; i++)
      circle(g, (i - 1) * 15 - 3, (i % 2) * 8 - 4, 4, "#f0d4ad33");
  }
  if (observed === -1) {
    g.shadowBlur = 0;
    circle(g, 0, 0, 37, null, "#c7416277");
    circle(g, 0, 0, 42, null, "#c7416222");
  }
  g.restore();
}
function habitat(event, now) {
  const { g, w, h } = fit("habitat");
  const bg = g.createRadialGradient(
    w * 0.5,
    h * 0.45,
    20,
    w * 0.5,
    h * 0.5,
    w * 0.7,
  );
  bg.addColorStop(0, "#f4ead4");
  bg.addColorStop(0.8, "#e0cba7");
  bg.addColorStop(1, "#b9a47f");
  g.fillStyle = bg;
  g.fillRect(0, 0, w, h);
  for (let i = 0; i < 380; i++) {
    const x = (((Math.sin(i * 78.2) * 4315.4) % 1) + 1) % 1,
      y = (((Math.sin(i * 123.6) * 1568.1) % 1) + 1) % 1;
    circle(g, x * w, y * h, 0.5, i % 2 ? "#775a3312" : "#fff8df44");
  }
  const r = Math.min(w * 0.43, h * 0.4);
  circle(g, w * 0.51, h * 0.47, r, null, "#927b5640");
  circle(g, w * 0.51, h * 0.47, r + 3, null, "#fff8dc77");
  circle(g, w * 0.51, h * 0.47, r + 7, null, "#80674418");
  for (let a = 0; a < 64; a++) {
    const angle = (a * Math.PI) / 32;
    line(
      g,
      [
        [
          w * 0.51 + Math.cos(angle) * (r + 2),
          h * 0.47 + Math.sin(angle) * (r + 2),
        ],
        [
          w * 0.51 + Math.cos(angle) * (r + (a % 4 === 0 ? 8 : 5)),
          h * 0.47 + Math.sin(angle) * (r + (a % 4 === 0 ? 8 : 5)),
        ],
      ],
      "#816f4b55",
      0.6,
    );
  }
  const done = phase() === 3;
  const fx = w * 0.6,
    fy = h * 0.46;
  for (let i = 0; i < 4; i++) {
    const a = i * 1.8 + 0.7;
    fruit(
      g,
      w * 0.5 + Math.cos(a) * r * 0.75,
      h * 0.47 + Math.sin(a) * r * 0.7,
      0.36,
      ["pear", "mixed", "banana"][i % 3],
      null,
    );
  }
  fruit(
    g,
    fx,
    fy,
    1,
    event?.family || "banana",
    done ? event?.observed_outcome : null,
  );
  const approach = Math.min(1, clock / 0.9),
    retreat =
      event && !event.neural.feeding && phase() === 3 ? (clock - 2.7) / 0.9 : 0;
  let x = w * 0.24 + (w * 0.37 - w * 0.24) * approach - retreat * w * 0.1,
    y = h * 0.5;
  const dead = event && !event.alive && done;
  g.save();
  g.translate(x, y);
  const walking = phase() === 0 || retreat > 0;
  drawSpecimen(
    g,
    Math.min(w * 0.13, 54),
    retreat > 0 ? Math.PI : 0,
    walking ? now * 8 : 0,
    palette.mint,
    dead,
  );
  if (event?.neural.feeding && phase() === 2) {
    const pulse = (Math.sin(now * 12) + 1) * 0.5;
    line(
      g,
      [
        [24, 0],
        [40 + pulse * 4, 0],
      ],
      "#765936",
      2,
    );
    circle(g, 41 + pulse * 4, 0, 3, "#977049");
  }
  g.restore();
  if (phase() === 1 && event?.recall.hits.length) {
    g.setLineDash([2, 4]);
    circle(g, x + 20, y, 55 + (Math.sin(now * 3) + 1) * 4, null, "#ad496376");
    g.setLineDash([]);
    text(g, "RECALL", x, y + 67, 8, "#92546b", "center");
  }
  if (done && event?.observed_outcome === -1) {
    g.fillStyle = "#ce365712";
    g.fillRect(0, 0, w, h);
    text(g, "SICKNESS OBSERVED", w - 17, h - 22, 8, "#a7445d", "right");
  } else if (done && event?.observed_outcome === 1)
    text(g, "NOURISHMENT OBSERVED", w - 17, h - 22, 8, "#697b45", "right");
}
const brainDots = [];
let rstate = 271;
function rand() {
  rstate = (1664525 * rstate + 1013904223) >>> 0;
  return rstate / 4294967296;
}
for (let side of [-1, 1])
  for (let i = 0; i < 650; i++) {
    const t = rand() * Math.PI * 2,
      r = Math.sqrt(rand()),
      optic = i < 250;
    brainDots.push({
      x: side * (optic ? 0.35 : 0.14) + Math.cos(t) * r * (optic ? 0.12 : 0.19),
      y: (optic ? 0.44 : 0.42) + Math.sin(t) * r * (optic ? 0.21 : 0.27),
      z: rand(),
      side,
    });
  }
const populations = [
  { name: "sugar", label: "SUGAR", x: -0.16, y: 0.78, color: palette.gold },
  { name: "bitter", label: "BITTER", x: 0.16, y: 0.78, color: palette.pink },
  { name: "FG", label: "HALT", x: -0.12, y: 0.41, color: palette.blue },
  { name: "P9-oDN1", label: "WALK", x: 0.19, y: 0.32, color: "#bbb1ec" },
  { name: "MN9", label: "FEED", x: 0, y: 0.6, color: palette.mint },
];
function traceValue(trial, name, bin) {
  const t = trial?.traces[name];
  if (!t) return 0;
  return Array.isArray(t[0])
    ? t.reduce((v, row) => v + (row[bin] || 0), 0)
    : t[bin] || 0;
}
function neuralBrain(event, now) {
  const { g, w, h } = fit("brain");
  for (const p of brainDots)
    circle(
      g,
      w * (0.5 + p.x),
      h * p.y,
      0.55 + p.z * 0.55,
      `rgba(143,155,194,${0.08 + p.z * 0.19})`,
    );
  const trial = recordings.get(event?.neural.trial_id),
    bin = Math.min(39, Math.floor((Math.max(0, clock - 1.8) / 0.9) * 40));
  for (const pop of populations) {
    const x = w * (0.5 + pop.x),
      y = h * pop.y;
    const count =
      phase() === 2
        ? traceValue(trial, pop.name, bin)
        : phase() === 3
          ? Array.from({ length: 40 }, (_, i) =>
              traceValue(trial, pop.name, i),
            ).reduce((a, b) => a + b, 0) / 40
          : 0;
    const active = count > 0;
    g.save();
    g.shadowColor = pop.color;
    g.shadowBlur = active ? 15 : 0;
    circle(
      g,
      x,
      y,
      active ? 8 + Math.min(count, 20) * 0.15 : 4,
      active ? pop.color : "#667090",
    );
    g.restore();
    if (active) {
      circle(g, x, y, 16 + (Math.sin(now * 8) + 1) * 4, null, pop.color + "55");
    }
    const left = pop.x <= 0,
      lx = x + (left ? -31 : 31);
    line(
      g,
      [
        [x + (left ? -8 : 8), y],
        [lx, y],
      ],
      pop.color + "66",
      0.7,
    );
    text(
      g,
      pop.label,
      lx + (left ? -3 : 3),
      y,
      7,
      pop.color,
      left ? "right" : "left",
    );
  }
  text(g, "POPULATION ACTIVITY", w * 0.5, h * 0.96, 7, "#747e9f", "center");
}
function spikeScope(event) {
  const { g, w, h } = fit("spikes"),
    trial = recordings.get(event?.neural.trial_id);
  const groups = [
    ["sugar", "SUGAR", palette.gold],
    ["bitter", "BITTER", palette.pink],
    ["MN9", "MN9 L", palette.mint],
  ];
  for (let row = 0; row < groups.length; row++) {
    const [name, title, color] = groups[row],
      y = 13 + row * 25;
    let values = trial?.traces[name] || Array(40).fill(0);
    if (Array.isArray(values[0])) values = values[0];
    const peak = Math.max(1, ...values);
    const visibleBins =
      phase() < 2
        ? 0
        : phase() === 2
          ? Math.ceil(((clock - 1.8) / 0.9) * 40)
          : 40;
    text(g, title, 16, y, 7, color);
    line(
      g,
      [
        [68, y + 7],
        [w - 15, y + 7],
      ],
      "#343851",
      0.5,
    );
    for (let i = 0; i < visibleBins; i++) {
      const x = 70 + (i * (w - 90)) / 40,
        height = (values[i] / peak) * 15;
      g.fillStyle =
        color +
        (phase() === 2 && i > Math.floor(((clock - 1.8) / 0.9) * 40)
          ? "35"
          : "bb");
      g.fillRect(x, y + 7 - height, Math.max(1, (w - 90) / 40 - 1), height);
    }
  }
  if (phase() === 2) {
    const x = 70 + Math.min(1, (clock - 1.8) / 0.9) * (w - 90);
    line(
      g,
      [
        [x, 2],
        [x, h - 4],
      ],
      "#ffffff55",
      1,
    );
  }
}
function memoryMap(event, now) {
  const { g, w, h } = fit("memory-map");
  g.strokeStyle = "#58628714";
  g.lineWidth = 0.6;
  for (let x = 20; x < w; x += 25) {
    g.beginPath();
    g.moveTo(x, 17);
    g.lineTo(x, h - 24);
    g.stroke();
  }
  for (let y = 20; y < h - 15; y += 25) {
    g.beginPath();
    g.moveTo(16, y);
    g.lineTo(w - 16, y);
    g.stroke();
  }
  const project = (p) => [
    w * 0.5 + p[0] * w * 0.39,
    h * 0.46 - p[1] * h * 0.37,
  ];
  const points = knownPoints(event),
    hits = new Set(phase() >= 1 ? event?.recall.hits.map((p) => p.id) : []),
    query = event ? project(event.map) : [w * 0.5, h * 0.5];
  mapPoints = [];
  for (const p of points) {
    const [x, y] = project(p.map),
      hit = hits.has(p.id),
      color = p.outcome === -1 ? palette.pink : palette.mint;
    mapPoints.push({ ...p, x, y });
    if (hit) {
      g.setLineDash([3, 5]);
      line(g, [[x, y], query], color + "88", 1);
      g.setLineDash([]);
      circle(g, x, y, 11 + (Math.sin(now * 3) + 1) * 2, null, color + "77");
    }
    if (p.id === selectedPoint) circle(g, x, y, 8, null, "#fff");
    g.save();
    g.shadowColor = color;
    g.shadowBlur = hit ? 12 : 5;
    circle(g, x, y, hit ? 4.5 : 3, color);
    g.restore();
    if (p.tick === event.step && phase() === 3)
      circle(g, x, y, 12 + (clock - 2.7) * 23, null, color + "66");
  }
  line(
    g,
    [
      [query[0] - 5, query[1]],
      [query[0] + 5, query[1]],
    ],
    "#fff",
    1.4,
  );
  line(
    g,
    [
      [query[0], query[1] - 5],
      [query[0], query[1] + 5],
    ],
    "#fff",
    1.4,
  );
  circle(g, ...query, 9, null, "#ffffff33");
  if (points.length === 0) {
    text(g, "No experiences yet.", w * 0.5, h * 0.7, 10, "#858ca6", "center");
  }
}
$("memory-map").onmousemove = (ev) => {
  const rect = ev.currentTarget.getBoundingClientRect(),
    x = ev.clientX - rect.left,
    y = ev.clientY - rect.top,
    p = mapPoints.find((p) => Math.hypot(p.x - x, p.y - y) < 10);
  const tip = $("map-tooltip");
  tip.hidden = !p;
  if (p) {
    tip.textContent = `Memory ${p.id} · ${p.outcome === -1 ? "harmful" : "nourishing"} · contact ${p.tick + 1}`;
    tip.style.left = Math.min(p.x + 10, rect.width - 155) + "px";
    tip.style.top = Math.max(0, p.y - 35) + "px";
  }
};
$("memory-map").onmouseleave = () => {
  $("map-tooltip").hidden = true;
};
$("memory-map").onclick = (ev) => {
  const r = ev.currentTarget.getBoundingClientRect(),
    p = mapPoints.find(
      (p) =>
        Math.hypot(p.x - (ev.clientX - r.left), p.y - (ev.clientY - r.top)) <
        12,
    );
  if (p) {
    selectedPoint = p.id;
    playing = false;
    render();
  }
};
function progress() {
  const { g, w, h } = fit("progress-chart");
  if (!result) return;
  const max = result.config.flies,
    n = result.config.encounters - 1;
  for (let y = 0; y < 3; y++) {
    const yy = 10 + (y * (h - 25)) / 2;
    line(
      g,
      [
        [19, yy],
        [w - 6, yy],
      ],
      "#30354a",
      0.7,
    );
    text(g, Math.round(max * (1 - y / 2)), 12, yy, 7, palette.muted, "right");
  }
  function plot(rows, color) {
    const points = rows
      .filter((p) => p.step <= (phase() === 3 ? step : step - 1))
      .map((p) => [
        20 + (p.step / n) * (w - 28),
        10 + (1 - p.alive / max) * (h - 25),
      ]);
    line(g, points, color, 1.8);
    const end = points.at(-1);
    if (end) circle(g, ...end, 3, color);
  }
  if (result.baseline) plot(result.baseline.curves, "#777d96");
  plot(result.curves, palette.mint);
  for (const tick of [0, Math.floor(n / 2), n])
    text(
      g,
      tick + 1,
      20 + (tick / n) * (w - 28),
      h - 3,
      7,
      palette.muted,
      "center",
    );
}
function render() {
  if (!result) return;
  const event = current(),
    p = phase(),
    done = p === 3,
    previousEvent = result.histories[subject][Math.max(0, event.step - 1)],
    stats = done
      ? event
      : event.step === 0
        ? { health: 100, safe_meals: 0, poison_meals: 0 }
        : previousEvent;
  $("subject").textContent = "FLY " + label(subject);
  $("contact-label").textContent =
    `Contact ${String(event.step + 1).padStart(2, "0")} / ${result.config.encounters}`;
  $("encounter-label").textContent =
    event.family === "mixed" ? "Fermented fruit" : event.family;
  $("safe-meals").textContent = stats.safe_meals;
  $("harmful-meals").textContent = stats.poison_meals;
  $("health-bar").style.width = stats.health + "%";
  $("health-bar").style.background =
    stats.health < 40 ? palette.pink : palette.mint;
  $("decision").textContent =
    !event.alive && done
      ? "Life ended"
      : done
        ? event.observed_outcome === -1
          ? "A bad meal."
          : event.observed_outcome === 1
            ? "Safely fed."
            : "Walks away."
        : [
            "Approaching",
            "Searching experience",
            event.neural.feeding ? "Feeding response" : "Feeding suppressed",
          ][p];
  $("memory-count").textContent = knownPoints(event).length;
  $("bitter-rate").textContent = p >= 1 ? event.neural.bitter_hz + " Hz" : "—";
  $("motor-rate").textContent =
    p >= 2 ? event.neural.readouts_hz.MN9[0] + " Hz" : "— Hz";
  $("motor-action").textContent =
    p >= 2
      ? event.neural.feeding
        ? "Feeds · >10 Hz"
        : "Refuses · ≤10 Hz"
      : "Awaiting input";
  $("motor-action").style.color =
    p >= 2
      ? event.neural.feeding
        ? palette.gold
        : palette.mint
      : palette.muted;
  $("trial-seed").textContent =
    `SEED ${event.neural.seed} · 1 SIMULATED SECOND`;
  $("neural-source").textContent = "RECORDED TRIAL";
  $("query-caption").textContent =
    `COSINE · TOP ${result.config.top_k} · ≥ ${result.config.threshold.toFixed(2)}`;
  const hits = p >= 1 ? event.recall.hits : [];
  $("match-count").textContent =
    hits.length + " MATCH" + (hits.length === 1 ? "" : "ES");
  $("matches").innerHTML = hits.length
    ? hits
        .map(
          (hit) =>
            `<div class="match ${hit.id === selectedPoint ? "selected" : ""}" role="button" tabindex="0" data-point="${hit.id}" aria-label="Select memory ${hit.id}"><i class="${hit.outcome === -1 ? "bitter-dot" : "safe-dot"}"></i><span>${hit.outcome === -1 ? "Harmful" : "Nourishing"}</span><span class="match-id">#${hit.id} · C${hit.tick + 1}</span><span class="score">${hit.score.toFixed(3)}</span><div class="match-track"><i style="width:${Math.max(0, hit.score) * 100}%"></i></div></div>`,
        )
        .join("")
    : `<p>${p === 0 ? "Preparing a query." : "No relevant earlier experience."}</p>`;
  document.querySelectorAll("[data-point]").forEach((row) => {
    const select = () => {
      selectedPoint = Number(row.dataset.point);
      playing = false;
      render();
    };
    row.onclick = select;
    row.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        select();
      }
    };
  });
  $("write-state").textContent = done
    ? event.write
      ? `Memory #${event.write.id} added`
      : event.neural.feeding
        ? "Memory disabled"
        : "No meal, no observed outcome"
    : "Awaiting observed outcome";
  const prePoints = knownPoints(event).filter((p) => p.tick < event.step);
  $("surgery").disabled = busy || prePoints.length === 0;
  $("verify").disabled = busy;
  $("scrub").value = step;
  $("replay-position").textContent =
    `${String(step + 1).padStart(2, "0")} / ${result.config.encounters}`;
  $("play").textContent = playing ? "Ⅱ" : "▶";
  $("play").setAttribute(
    "aria-label",
    playing ? "Pause replay" : "Play replay",
  );
  document
    .querySelectorAll("[data-phase]")
    .forEach((node) =>
      node.classList.toggle("active", Number(node.dataset.phase) === p),
    );
  const details = [
    "A new smell enters the loop.",
    `${hits.length} actual Edge match${hits.length === 1 ? "" : "es"}. Evidence ${event.recall.evidence.toFixed(2)}.`,
    `Sugar 150 Hz + recalled bitter ${event.neural.bitter_hz} Hz.`,
    event.write
      ? `Observed outcome written to personal memory #${event.write.id}.`
      : "Only observed meals can create memories.",
  ][p];
  $("loop-detail").textContent = details;
  const displayedStep = p === 3 ? step : step - 1;
  const curve =
    displayedStep < 0
      ? { alive: result.config.flies, safe_meals: 0, poison_meals: 0 }
      : result.curves[displayedStep];
  const complete = displayedStep === result.config.encounters - 1;
  $("alive-count").innerHTML =
    `${complete ? result.summary.thriving : curve.alive}<span>/${result.config.flies}</span>`;
  $("cohort-metric").textContent = complete ? "SURVIVED + FED" : "ALIVE";
  $("thriving-count").textContent = complete
    ? `${result.summary.minimum_safe_meals} safe meals minimum`
    : `Goal: survive + ${result.summary.minimum_safe_meals} safe meals`;
  $("progress-result").textContent =
    `${curve.safe_meals} safe meals · ${curve.poison_meals} harmful meals`;
  $("roster").innerHTML = result.histories
    .map((history, i) => {
      const e =
        displayedStep < 0
          ? { alive: true, health: 100 }
          : history[Math.min(displayedStep, history.length - 1)];
      return `<button class="${i === subject ? "current " : ""}${!e.alive ? "lost" : ""}" aria-label="Fly ${label(i)}, ${e.alive ? "alive" : "life ended"}" aria-pressed="${i === subject}" data-fly="${i}">${label(i)}<i class="life" style="width:${e.health}%"></i></button>`;
    })
    .join("");
  document.querySelectorAll("[data-fly]").forEach(
    (b) =>
      (b.onclick = () => {
        subject = Number(b.dataset.fly);
        selectedPoint = null;
        render();
      }),
  );
  progress();
}
async function verify() {
  const event = current();
  if (!event || busy) return;
  playing = false;
  working(true, "LIVE · running the full brain");
  $("neural-source").textContent = "LIVE · COMPUTING";
  const started = performance.now(),
    timer = setInterval(() => {
      $("neural-source").textContent =
        `LIVE · ${Math.floor((performance.now() - started) / 1000)}s`;
    }, 1000);
  try {
    const verified = await api("/api/verify", {
      trial_id: event.neural.trial_id,
    });
    if (!verified.matches_recording)
      throw Error(
        "Live response differs from the recorded trial. Inspect the response and source versions.",
      );
    $("neural-source").textContent =
      `LIVE VERIFIED · ${verified.wall_seconds.toFixed(1)}s`;
    $("experiment-state").textContent =
      "Live spikes match the recorded readouts.";
  } catch (e) {
    error(e.message);
    $("neural-source").textContent = "RECORDED TRIAL";
  } finally {
    clearInterval(timer);
    working(false, "Live verification finished");
  }
}
$("verify").onclick = verify;
function surgeryResult(data) {
  $("intervention-context").textContent =
    `Fly ${label(data.fly)} · contact ${data.step + 1} · memory #${data.point_id} · ${data.source === "live" ? "live neural calculations" : "recorded neural trials"}`;
  const stages = [
    ["before", "MEMORY PRESENT"],
    ["after", "MEMORY DELETED"],
    ["restored", "MEMORY RESTORED"],
  ];
  $("intervention-results").innerHTML =
    '<div class="intervention-grid">' +
    stages
      .map(([key, name]) => {
        const row = data[key],
          n = row.neural;
        return `<div class="intervention-card ${key === "after" ? "changed" : ""}"><small>${name}</small><strong>${n.readouts_hz.MN9[0]} <small>Hz</small></strong><span class="outcome">${n.feeding ? "Feeds" : "Refuses"}</span><span class="details">Bitter ${n.bitter_hz} Hz<br>${row.recall.hits.length} retrieved memories<br>${n.source === "live" ? "LIVE" : "RECORDED"} · seed ${n.seed}</span></div>`;
      })
      .join("") +
    "</div>";
  $("intervention-verdict").textContent = !data.restored_decision
    ? "Restoration did not reproduce the decision. Repeat the experiment and inspect the responses."
    : data.changed_decision
      ? "One missing experience changed the motor response. Restoring it restored the decision."
      : "The decision held. Other memories or a weak recall can make this point redundant. Try an earlier recall.";
  $("live-surgery").disabled = false;
}
async function surgery(live = false) {
  const event = current();
  if (!event || busy) return;
  playing = false;
  if (!live) {
    const points = knownPoints(event).filter((p) => p.tick < event.step);
    const id = selectedPoint ?? event.recall.hits[0]?.id ?? points.at(-1)?.id;
    if (!id) return;
    interventionRequest = {
      run_id: result.id,
      fly: subject,
      step: event.step,
      point_id: id,
    };
    $("intervention-dialog").showModal();
    $("intervention-context").textContent =
      `Fly ${label(subject)} · contact ${event.step + 1} · memory #${id} · ${live ? "live" : "recorded neural trials"}`;
  }
  working(
    true,
    live
      ? "LIVE · comparing three neural responses"
      : "Deleting and restoring a real Qdrant point",
  );
  $("intervention-verdict").textContent = "";
  $("intervention-results").textContent = live
    ? "Running three whole-brain trials. This takes about 30 seconds."
    : "Querying before deletion, after deletion, and after restoration…";
  try {
    const data = await api("/api/intervention", {
      ...interventionRequest,
      live,
    });
    surgeryResult(data);
  } catch (e) {
    error(e.message);
    $("intervention-results").textContent = e.message;
  } finally {
    working(false, "Memory intervention finished");
  }
}
$("surgery").onclick = () => surgery(false);
$("live-surgery").onclick = () => surgery(true);
for (const button of document.querySelectorAll("dialog .close"))
  button.onclick = () => button.closest("dialog").close();
$("benchmark").onclick = async () => {
  if (busy) return;
  playing = false;
  $("benchmark-dialog").showModal();
  $("benchmark-results").textContent = "Running ten matched experiments…";
  working(true, "Comparing policies across two cohorts");
  try {
    const data = await api("/api/benchmark", config());
    $("benchmark-results").innerHTML = [2000, 3000]
      .map(
        (seed) =>
          `<div class="cohort-label">${seed === 2000 ? "Calibration" : "Held-out"} cohort · seed ${seed}</div><table><thead><tr><th>POLICY</th><th>SURVIVED + FED</th><th>SAFE MEALS</th><th>HARMFUL</th><th>SAFE REFUSALS</th></tr></thead><tbody>${data.results
            .filter((r) => r.config.seed === seed)
            .map(
              (r) =>
                `<tr><td>${esc(r.config.mode)}</td><td class="${r.summary.thriving ? "good" : ""}">${r.summary.thriving}/${r.config.flies}</td><td>${r.summary.safe_meals}</td><td>${r.summary.poison_meals}</td><td>${r.summary.safe_refusals}</td></tr>`,
            )
            .join("")}</tbody></table>`,
      )
      .join("");
  } catch (e) {
    $("benchmark-results").textContent = e.message;
  } finally {
    working(false, "Comparison finished");
  }
};
async function init() {
  try {
    const data = await Promise.all([api("/api/brain"), api("/api/status")]);
    bank = data[0];
    for (const row of bank.trials) recordings.set(row.id, row);
    $("engine").innerHTML =
      `<i></i>Qdrant Edge${data[1].exercise ? " · exercise" : ""}`;
    await run();
  } catch (e) {
    error(e.message);
    $("experiment-state").textContent = "Setup needs attention";
  }
}
function frame(now) {
  const delta = previous ? Math.min(0.1, (now - previous) / 1000) : 0;
  previous = now;
  if (result && playing && !busy) {
    clock += delta * Number($("speed").value);
    if (clock >= 3.6) {
      if (step < result.config.encounters - 1) {
        step++;
        clock = 0;
        selectedPoint = null;
      } else {
        clock = 3.6;
        playing = false;
      }
    }
  }
  const event = current();
  habitat(event, now / 1000);
  neuralBrain(event, now / 1000);
  spikeScope(event);
  memoryMap(event, now / 1000);
  const key = result
    ? `${result.id}/${subject}/${step}/${phase()}/${playing}`
    : "";
  if (frame.key !== key) {
    frame.key = key;
    render();
  }
  requestAnimationFrame(frame);
}
window.addEventListener("resize", () => {
  if (result) render();
});
init();
requestAnimationFrame(frame);
