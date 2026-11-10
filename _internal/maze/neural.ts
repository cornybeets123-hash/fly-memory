// Closed-loop heading worker for the agreed maze integration gate.
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {createInterface} from 'node:readline';
import {parseGraph,parseNeurons} from '../brain/data.ts';
import {LIFEngine,SHIU_PARAMS} from '../brain/engine.ts';

const data=new URL('../brain/data/',import.meta.url);
const meta=JSON.parse(readFileSync(new URL('meta.json',data),'utf8'));
const ab=(b:Buffer)=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
const graph=parseGraph(ab(gunzipSync(readFileSync(new URL('graph.bin.gz',data)))),meta);
const info=parseNeurons(ab(gunzipSync(readFileSync(new URL('neurons.bin.gz',data)))),meta.neurons);
const types=new Set(['DNa02','DNa01','DNae002','DNg111','DNb01','DNge043']);
const left:number[]=[],right:number[]=[];
for(let i=0;i<graph.n;i++)if(types.has(meta.types[info.type[i]])){
 if(info.side[i]===1)left.push(i);if(info.side[i]===2)right.push(i);
}
const weights=new Float32Array(graph.syn.length);
for(let i=0;i<weights.length;i++)weights[i]=graph.syn[i]*SHIU_PARAMS.wSyn;
const calEngine=new LIFEngine(graph,SHIU_PARAMS,99,weights);calEngine.defineGroups([left,right]);
function measure(side:number){calEngine.reset();calEngine.setRate(meta.groups.LC10a_L,side===0?50:0);calEngine.setRate(meta.groups.LC10a_R,side===1?50:0);calEngine.groupCounts.fill(0);calEngine.run(6000);calEngine.drainSpikes();return calEngine.groupCounts[side]/.6;}
const responseL=measure(0),responseR=measure(1),reference=(responseL+responseR)/2;
const calibration={responseL,responseR,reference,gainL:reference/responseL,gainR:reference/responseR};
const sessions=new Map<string,{engine:LIFEngine,rateL:number,rateR:number}>();
function command(q:any){
 if(q.command==='info')return {neurons:graph.n,connections:graph.syn.length,calibration,readout:{left,right},groups:{left:meta.groups.LC10a_L,right:meta.groups.LC10a_R}};
 if(q.command==='drop'){sessions.delete(q.fly);return {ok:true};}
 if(q.command!=='step')throw Error('Unknown command');
 if(q.ms!==20||![q.left,q.right].every(v=>Number.isFinite(v)&&v>=0&&v<=80))throw Error('Invalid sensory frame');
 let s=sessions.get(q.fly);
 if(!s){const engine=new LIFEngine(graph,SHIU_PARAMS,q.seed,weights);engine.defineGroups([left,right]);s={engine,rateL:0,rateR:0};sessions.set(q.fly,s);}
 const e=s.engine;e.setRate(meta.groups.LC10a_L,q.left);e.setRate(meta.groups.LC10a_R,q.right);e.groupCounts.fill(0);e.inputEvents=[];e.run(200);
 const spikes=e.takeSpikes(),k=1-Math.exp(-20/55);
 s.rateL+=(e.groupCounts[0]*50-s.rateL)*k;s.rateR+=(e.groupCounts[1]*50-s.rateR)*k;
 const steer=Math.max(-1,Math.min(1,(calibration.gainR*s.rateR-calibration.gainL*s.rateL)/(reference*.75)));
 return {steer,left:e.groupCounts[0],right:e.groupCounts[1],rateL:s.rateL,rateR:s.rateR,spikes:spikes.ids.length,ids:q.trace?[...new Set(spikes.ids)]:[],time_ms:e.timeMs};
}
for await(const line of createInterface({input:process.stdin})){
 try{process.stdout.write(JSON.stringify({result:command(JSON.parse(line))})+'\n');}
 catch(error){process.stdout.write(JSON.stringify({error:String(error)})+'\n');}
}
