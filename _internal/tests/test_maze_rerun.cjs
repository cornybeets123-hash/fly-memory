const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function harness(){
  const noop=()=>{},graphics=new Proxy({}, {get:(o,k)=>k in o?o[k]:noop});
  class Element{
    constructor(id){this.id=id;this.disabled=false;this.style={};this.dataset={};this.classList={toggle:noop,remove:noop};}
    getBoundingClientRect(){return {width:450,height:250};}getContext(){return graphics;}
    addEventListener(){}setAttribute(){}replaceChildren(){}showModal(){}close(){}
  }
  const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);};
  const stages=['none','personal','shared'].map(mode=>{const e=new Element(mode);e.dataset.mode=mode;return e;});
  const document={body:{dataset:{}},getElementById:get,querySelectorAll:()=>stages,createElement:()=>new Element('created'),createTextNode:()=>new Element('text'),addEventListener:noop,documentElement:{}};
  const world={bounds:[0,0,860,660],rectangles:[],walls:[],landmarks:[],start:[260,580,-Math.PI/2],exit:[825,620]};
  function result(mode){return {mode,seed:2000,summary:{time_ms:1000,exit:true},events:[],decisions:[],observations:[],frames:[{ms:20,x:260,y:580,heading:-Math.PI/2,left_input:0,right_input:0,neural:{ids:[],left:0,right:0}}]};}
  let requests=0,fail=false,deferred=null,truncated=false,hold=null;
  const encoder=new TextEncoder();
  const fetch=async(url,options)=>{
    if(url.includes('positions'))return {ok:true,arrayBuffer:async()=>new Float32Array([0,0,10,10]).buffer};
    if(url.includes('status'))return {ok:true,json:async()=>({world})};
    requests++;if(fail)throw Error('Deliberate request failure');
    if(deferred)await new Promise(resolve=>deferred=resolve);
    const {mode}=JSON.parse(options.body);
    const data={mode,flies:Array.from({length:8},(_,i)=>({...result(mode),owner:`A${i+1}`})),comparisons:[],world,brain:{readout:{left:[],right:[]}},initial_memories:[],cohort:{}};
    const messages=[{type:'begin',data},{type:'batch',ms:1000,flies:data.flies.map((fly,index)=>({index,frames:[],events:[],decisions:[],observations:[],summary:fly.summary}))}];
    if(!truncated)messages.push({type:'complete',summary:{count:8}});
    const pieces=messages.map(message=>encoder.encode(`data: ${JSON.stringify(message)}\n\n`));
    let index=0,offset=0;
    return {ok:true,body:{getReader:()=>({
      async read(){
        if(index===1&&offset===0&&hold)await new Promise(resolve=>hold=resolve);
        if(index===pieces.length)return {done:true};
        const value=pieces[index].slice(offset,offset+17);offset+=value.length;
        if(offset===pieces[index].length){index++;offset=0;}
        return {value,done:false};
      },async cancel(){},releaseLock(){}
    })}};
  };
  const window={devicePixelRatio:1,matchMedia:()=>({matches:false}),addEventListener:noop};
  const context=vm.createContext({window,document,fetch,requestAnimationFrame:noop,console,TextDecoder,structuredClone});
  vm.runInContext(fs.readFileSync('_internal/maze/static/app.js','utf8')+'\nglobalThis.api={start,ready,tick,setMode:v=>mode=v,state:()=>({busy,playing,elapsed,count:bundle?.flies.length,streaming:bundle?.streaming}),addMatch:()=>bundle.hero.decisions.push({time:100,choice:0,views:[{hits:[],selected:{score:1,payload:{source_fly:"A6",outcome:"returned"}},applied:true,bearing:0}]})};',context);
  return {api:context.api,get,requests:()=>requests,setFail:v=>fail=v,truncate:v=>truncated=v,hold:()=>hold=true,continue:()=>{const done=hold;hold=null;done();},defer:()=>deferred=true,release:()=>{const done=deferred;deferred=null;done();}};
}
for(const mode of ['none','personal','shared'])test(`${mode}: rerun, busy guard, and recovery`,async()=>{
  const h=harness();await h.api.ready;h.api.setMode(mode);
  await h.api.start();await h.api.start();assert.equal(h.requests(),2);assert.equal(h.get('run').disabled,false);
  h.defer();const pending=h.api.start();await Promise.resolve();await h.api.start();assert.equal(h.requests(),3);h.release();await pending;
  h.setFail(true);await h.api.start();assert.match(h.get('message').textContent,/Deliberate request failure/);assert.equal(h.get('run').disabled,false);assert.equal(h.api.state().busy,false);
  h.setFail(false);await h.api.start();assert.equal(h.api.state().playing,true,h.get('message').textContent);assert.equal(h.get('run').disabled,false);
});

test('all eight flies are visible before computation completes',async()=>{
  const h=harness();await h.api.ready;h.hold();const pending=h.api.start();
  while(!h.api.state().streaming)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(h.api.state().count,8);assert.equal(h.api.state().playing,true,h.get('message').textContent);assert.equal(h.api.state().busy,true);
  assert.equal(h.get('pause').disabled,false);h.continue();await pending;
  assert.equal(h.api.state().streaming,false);
});
test('a truncated stream stops playback and permits recovery',async()=>{
  const h=harness();await h.api.ready;h.truncate(true);await h.api.start();
  assert.match(h.get('message').textContent,/ended before the group finished/);
  assert.equal(h.api.state().playing,false);assert.equal(h.get('run').disabled,false);
  h.truncate(false);await h.api.start();assert.equal(h.api.state().playing,true,h.get('message').textContent);
});
test('retrieved evidence does not freeze the clock',async()=>{
  const h=harness();await h.api.ready;await h.api.start();h.api.addMatch();
  h.api.tick(100);h.api.tick(180);assert.equal(h.api.state().elapsed,160);
  h.api.tick(260);assert.equal(h.api.state().elapsed,320);
});
