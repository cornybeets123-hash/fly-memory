// Independent dense integration checks the lazy-update optimization on the full graph.
import {readFileSync, writeFileSync} from "node:fs";
import {gunzipSync} from "node:zlib";
import {parseGraph} from "./data.ts";
import {LIFEngine, SHIU_PARAMS as p} from "./engine.ts";
const D = new URL("../data/", import.meta.url);
const meta = JSON.parse(readFileSync(new URL("meta.json", D), "utf8"));
const b = gunzipSync(readFileSync(new URL("graph.bin.gz", D)));
const graph = parseGraph(b.buffer.slice(b.byteOffset, b.byteOffset+b.byteLength), meta);
const input = ["LPLC2_L","LPLC2_R","LC4_L","LC4_R"].flatMap(k=>meta.groups[k]);
const motor = new Set<number>([...meta.groups.DNp01_L,...meta.groups.DNp01_R]);
const steps = 1000;
const results = [];
for (const [seed,persistent] of [[7,false],[11,false],[23,false],[7,true]] as const) {
  const trialSteps = persistent ? 4000 : steps;
  const fast = new LIFEngine(graph,p,seed);
  fast.setRate(input,150);
  let replayed: Array<[number,number]> = [];
  const cue = meta.groups.LC10a_L;
  if(persistent) {
    fast.setRate(cue,20);
    fast.run(800);
    replayed = fast.inputEvents.slice();
    fast.setRate(input,0);
    fast.run(1200);
    fast.replay(replayed,800,[...input,...cue]);
    fast.run(2000);
  } else fast.run(steps);
  const spikes = fast.takeSpikes();
  const events = new Map<number,number[]>();
  for (const [step,i] of fast.inputEvents) {const row=events.get(step)??[];row.push(i);events.set(step,row);}
  for(const [step,i] of replayed){const at=step+2000;const row=events.get(at)??[];row.push(i);events.set(at,row);}
  const stimulated = new Set(input), cueSet = new Set<number>(cue);
  const u = new Float32Array(graph.n), g = new Float32Array(graph.n), ref = new Uint16Array(graph.n);
  const delayed: number[][] = Array.from({length:18},()=>[]);
  const ids:number[] = [], times:number[] = [];
  const a=Math.exp(-p.dt/p.tauM),bb=Math.exp(-p.dt/p.tauS),c=p.tauS/(p.tauS-p.tauM)*(bb-a);
  for(let t=0;t<trialSteps;t++) {
    const due=delayed[t%18];
    for(const pre of due)for(let edge=graph.indptr[pre];edge<graph.indptr[pre+1];edge++)g[graph.post[edge]]+=fast.w[edge];
    const emitted:number[]=[];
    for(const i of events.get(t)??[])u[i]+=p.poissonWeight;
    for(let i=0;i<graph.n;i++) {
      if(ref[i]){ref[i]--;continue;}
      const next=a*u[i]+c*g[i];
      const current=bb*g[i];
      if(next>7){u[i]=0;g[i]=0;ref[i]=((stimulated.has(i)&&(!persistent||t<800||(t>=2000&&t<2800)))||(persistent&&cueSet.has(i)))?0:22;ids.push(i);times.push(t);emitted.push(i);}
      else {u[i]=next;g[i]=current;}
    }
    delayed[t%18]=emitted;
  }
  const fastMotor:number[]=[],denseMotor:number[]=[];
  for(let i=0;i<spikes.ids.length;i++)if(motor.has(spikes.ids[i]))fastMotor.push(spikes.steps[i]);
  for(let i=0;i<ids.length;i++)if(motor.has(ids[i]))denseMotor.push(times[i]);
  const row={seed,persistent_replay:persistent,ms:trialSteps*.1,fast_spikes:spikes.ids.length,dense_spikes:ids.length,relative_spike_difference:Math.abs(ids.length-spikes.ids.length)/ids.length,
    fast_motor_ms:fastMotor.map(t=>t*.1),dense_motor_ms:denseMotor.map(t=>t*.1),motor_times_equal:JSON.stringify(fastMotor)===JSON.stringify(denseMotor)};
  results.push(row);
  if(!row.motor_times_equal || row.relative_spike_difference>.01)throw new Error(JSON.stringify(row));
}
const output={scope:"Full FlyWire v783 graph, fixed external events, independent dense Float32 integration. This checks the lazy optimizer, not equivalence to Brian2 scheduling or biology.",results};
if(process.argv[2])writeFileSync(process.argv[2],JSON.stringify(output,null,2));
console.log(JSON.stringify(output));
