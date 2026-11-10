// Local JSON-lines worker. No browser automation or external service calls.
import {readFileSync} from "node:fs";
import {gunzipSync} from "node:zlib";
import {createHash} from "node:crypto";
import {createInterface} from "node:readline";
import {parseGraph} from "./data.ts";
import {LIFEngine, SHIU_PARAMS} from "./engine.ts";

const DATA = new URL("../data/", import.meta.url);
const meta = JSON.parse(readFileSync(new URL("meta.json", DATA), "utf8"));
const buf = gunzipSync(readFileSync(new URL("graph.bin.gz", DATA)));
const graph = parseGraph(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), meta);
const loom = ["LPLC2_L", "LPLC2_R", "LC4_L", "LC4_R"].flatMap(k => meta.groups[k]);
const loomSet = new Set<number>(loom);
const motor = new Set<number>([...meta.groups.DNp01_L, ...meta.groups.DNp01_R]);
const cue = meta.groups.LC10a_L;
const weights = new Float32Array(graph.syn.length);
for (let i = 0; i < weights.length; i++) weights[i] = graph.syn[i] * SHIU_PARAMS.wSyn;
const disconnected = weights.slice();
for (const i of loom) disconnected.fill(0, graph.indptr[i], graph.indptr[i + 1]);
const sessions = new Map<string, LIFEngine>();
const recordings = new Map<string, {events: Array<[number, number]>, steps: number, targets: number[]}>();
const PROTOCOL = "flywire-v783-doodle-2a8a031-escape-v1";

function respond(req: any) {
  if (req.command === "info") return {protocol: PROTOCOL, neurons: graph.n, connections: graph.syn.length, params: SHIU_PARAMS};
  if (req.command === "clear") {sessions.clear(); recordings.clear(); return {ok: true};}
  if (req.command !== "encounter") throw new Error("Unknown command");
  if (req.replay && !recordings.has(req.replay)) throw new Error("Unknown input recording");
  let engine = sessions.get(req.fly);
  if (!engine) {
    engine = new LIFEngine(graph, SHIU_PARAMS, req.seed, req.disconnect ? disconnected : weights);
    sessions.set(req.fly, engine);
  }
  const base = engine.step;
  engine.takeSpikes();
  engine.inputEvents = [];
  for (const id of cue) engine.setRate([id], 20);
  const stored = req.replay ? recordings.get(req.replay)! : null;
  if (stored) engine.replay(stored.events, stored.steps, stored.targets);
  const naturalStart = 200 - req.lead_ms;
  const naturalStop = naturalStart + 80;
  let firstMotor: number | null = null;
  let motorCount = 0;
  let spikes = 0;
  const active = new Set<number>();
  const trace: Array<{ms: number, ids: number[], motor: number, input: number}> = [];
  const digest = createHash("sha256");
  for (let ms = 0; ms < 600; ms += 5) {
    if (req.threat && ms === naturalStart) engine.setRate(loom, 150);
    if (req.threat && ms === naturalStop) engine.setRate(loom, 0);
    if (ms === 300) engine.setRate(cue, 0);
    engine.run(50);
    const out = engine.takeSpikes();
    let dn = 0, input = 0;
    const ids = new Set<number>();
    for (let k = 0; k < out.ids.length; k++) {
      const id = out.ids[k];
      active.add(id); ids.add(id);
      if (loomSet.has(id)) input++;
      if (motor.has(id)) {
        motorCount++; dn++;
        if (firstMotor === null) firstMotor = (out.steps[k] - base) * .1;
      }
    }
    spikes += out.ids.length;
    digest.update(Buffer.from(out.ids.buffer));
    digest.update(Buffer.from(out.steps.buffer));
    if (req.trace && ms < 350) trace.push({ms, ids: [...ids], motor: dn, input});
  }
  // Only externally observed input can become a recording, including safe episodes.
  // Recalled events never enter inputEvents and cannot become new observations.
  const events = engine.inputEvents.filter(([t]) => t >= base + naturalStart * 10 && t < base + naturalStop * 10)
    .map(([t, i]) => [t - base - naturalStart * 10, i] as [number, number]);
  const captured = {events, steps: 800, targets: [...cue, ...(req.threat ? loom : [])]};
  const recording = createHash("sha256").update(PROTOCOL).update(JSON.stringify(captured)).digest("hex");
  recordings.set(recording, captured);
  return {
    protocol: PROTOCOL, first_motor_ms: firstMotor === null ? null : Number(firstMotor.toFixed(1)),
    motor_spikes: motorCount, active_neurons: active.size, spikes, trace,
    recording, recording_events: events.length, recording_duration_ms: 80,
    spike_hash: digest.digest("hex"), start_ms: base * .1, end_ms: engine.timeMs,
    replay_events: stored?.events.length ?? 0,
    natural_input_hash: createHash("sha256").update(JSON.stringify(engine.inputEvents.map(([t,i])=>[t-base,i]))).digest("hex"),
  };
}

const reader = createInterface({input: process.stdin});
for await (const line of reader) {
  try {process.stdout.write(JSON.stringify({result: respond(JSON.parse(line))}) + "\n");}
  catch (error) {process.stdout.write(JSON.stringify({error: String(error)}) + "\n");}
}
