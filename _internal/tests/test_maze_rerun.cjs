const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function harness(offline=false){
  const noop=()=>{},graphics=new Proxy({}, {get:(o,k)=>k in o?o[k]:noop});
  class Element{
    constructor(id){this.id=id;this.disabled=false;this.style={};this.dataset={};const classes=new Set();this.classList={toggle:(name,on)=>on?classes.add(name):classes.delete(name),remove:name=>classes.delete(name),contains:name=>classes.has(name)};}
    getBoundingClientRect(){return {width:450,height:250};}getContext(){return graphics;}
    addEventListener(){}setAttribute(){}replaceChildren(...children){this.children=children;}showModal(){}close(){}
  }
  const specimens=[];
  const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);};
  const stages=['none','personal','shared'].map(mode=>{const e=new Element(mode);e.dataset.mode=mode;return e;});
  const document={body:{dataset:{}},getElementById:get,querySelectorAll:()=>stages,createElement:()=>new Element('created'),createTextNode:()=>new Element('text'),addEventListener:noop,documentElement:{}};
  const world={bounds:[0,0,860,660],rectangles:[],walls:[],landmarks:[],start:[260,580,-Math.PI/2],exit:[825,620]};
  function result(mode){return {mode,seed:2000,summary:{time_ms:1000,exit:true},events:[],decisions:[],observations:[],frames:[{ms:20,x:260,y:580,heading:-Math.PI/2,left_input:0,right_input:0,neural:{ids:[],left:0,right:0}}]};}
  const sentSeeds=[];
  let requests=0,fail=false,deferred=null,truncated=false,hold=null;
  const encoder=new TextEncoder();
  const fetch=async(url,options)=>{
    if(url.includes('positions'))return {ok:true,arrayBuffer:async()=>new Float32Array([0,0,10,10]).buffer};
    if(url.includes('status'))return {ok:true,json:async()=>({world})};
    requests++;sentSeeds.push(JSON.parse(options.body).seed);if(fail)throw Error('Deliberate request failure');
    if(deferred)await new Promise(resolve=>deferred=resolve);
    const {mode,seed:requestedSeed}=JSON.parse(options.body);
    const data={mode,flies:Array.from({length:8},(_,i)=>({...result(mode),seed:requestedSeed+i,owner:`A${i+1}`})),comparisons:[],world,brain:{readout:{left:[],right:[]}},initial_memories:[],cohort:{}};
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
  if(offline)window.WORKSHOP_DATA={world,positions_b64:Buffer.from(new Float32Array([0,0,10,10]).buffer).toString('base64'),runs:Object.fromEntries(['none','personal','shared'].map(mode=>[`${mode}:normal`,{mode,flies:Array.from({length:8},(_,i)=>({...result(mode),owner:`${mode==='shared'?'B':'A'}${i+1}`})),comparisons:[],world,brain:{readout:{left:[],right:[]}},initial_memories:[],cohort:{}}]))};
  const context=vm.createContext({window,document,fetch,atob,Math:Object.assign(Object.create(Math),{random:()=>.345678}),drawSpecimen:(g,size,heading)=>specimens.push({size,heading}),requestAnimationFrame:noop,console,TextDecoder,structuredClone});
  vm.runInContext(fs.readFileSync('_internal/maze/static/app.js','utf8')+'\nglobalThis.api={start,ready,tick,junctionEvidence,viewRotation,imageInto,drawWorld,replayMemory,toggleSteering,addDecision:decision=>bundle.hero.decisions.push(decision),addFrame:frame=>bundle.hero.frames.push(frame),setEvidence:(decision,time,observations=[])=>{bundle.hero.decisions=[decision];bundle.initial_memories=observations;elapsed=time;lastEvidence="";update();},setMode:v=>mode=v,state:()=>({seed,busy,playing,elapsed,disconnected,bundleDisconnected:bundle?.disconnected,count:bundle?.flies.length,streaming:bundle?.streaming}),addMatch:()=>bundle.hero.decisions.push({time:100,choice:0,views:[{hits:[],selected:{score:1,payload:{source_fly:"A6",outcome:"returned"}},applied:true,bearing:0}]})};',context);
  return {api:context.api,get,specimens,sentSeeds,requests:()=>requests,setFail:v=>fail=v,truncate:v=>truncated=v,hold:()=>hold=true,continue:()=>{const done=hold;hold=null;done();},defer:()=>deferred=true,release:()=>{const done=deferred;deferred=null;done();}};
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

function junction({applied=true,hits=true,rates=[0,30],choice=1}={}){
  const hit={id:'observed',score:.9755,payload:{source_fly:'A3',outcome:'returned',snapshot:'observed-view'}};
  return {time:100,capture_time:20,candidates:[0,1],choice,decision_input:rates,decision_readout:.63,views:[
    {bearing:-1,hits:hits?[hit]:[],selected:applied?hit:null,applied,search_ms:.025,image_url:'query'},
    {bearing:1,hits:[],selected:null,applied:false,search_ms:.014,image_url:'other-query'}
  ]};
}
test('a retrieved observation explains the exact input and neural choice',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('shared');await h.api.start();
  const d=junction();h.api.setEvidence(d,100,[{id:'observed',payload:d.views[0].selected.payload,image_url:'stored'}]);
  assert.equal(h.get('current-caption').textContent,'Left view');
  assert.equal(h.get('cosine-score').textContent,'0.976');
  assert.equal(h.get('search-time').textContent,'0.03');
  assert.equal(h.get('provenance').textContent,'A3 observed it. A6 uses it.');
  assert.equal(h.get('left-input').textContent,'0');assert.equal(h.get('right-input').textContent,'30');
  assert.equal(h.get('left-option').classList.contains('suppressed'),true);
  assert.equal(h.get('policy').textContent,'Memory suppresses the left option.');
  assert.equal(h.get('decision-choice').textContent,'→');
  assert.equal(h.get('junction-time').textContent,'Last memory use · 0.1 s');
});
test('returned evidence does not imply an applied exclusion',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  h.api.setEvidence(junction({applied:false,rates:[30,30]}),100);
  assert.equal(h.get('returned-count').textContent,'1');
  assert.equal(h.get('input-panel').classList.contains('applied'),false);
  assert.equal(h.get('left-option').classList.contains('suppressed'),false);
  assert.equal(h.get('policy').textContent,'Both options enter the brain.');
  assert.match(h.get('provenance').textContent,/input stays unchanged/);
});
test('an empty search and a missing junction keep input states honest',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  assert.equal(h.get('left-input').textContent,'—');
  h.api.setEvidence(junction({applied:false,hits:false,rates:[30,30]}),100);
  assert.equal(h.get('returned-count').textContent,'0');assert.equal(h.get('cosine-score').textContent,'—');
  assert.equal(h.get('memory-title').textContent,'No match ≥ 0.90.');
  assert.equal(h.get('policy').textContent,'Both options enter the brain.');
});
test('the last junction stays labelled while current steering and time advance',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  h.api.setEvidence(junction(),100);h.api.tick(100);h.api.tick(180);
  assert.equal(h.api.state().elapsed,260);
  assert.equal(h.get('junction-time').textContent,'Last memory use · 0.1 s');
  assert.equal(h.get('left-input').textContent,'0');
  assert.equal(h.get('input').textContent,'Steering input: 0 / 0 Hz');
});

test('returned evidence outside the sensory mapping does not highlight brain input',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('shared');await h.api.start();
  const d=junction({rates:[30,30]});d.views.push({...d.views[0]});d.views[0].applied=false;
  h.api.setEvidence(d,100);
  assert.equal(h.get('input-panel').classList.contains('applied'),false);
  assert.equal(h.get('left-input').textContent,'30');
});
test('all-excluded recovery displays the actual balanced inputs',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  const d=junction({rates:[30,30]});d.all_excluded=true;
  h.api.setEvidence(d,100);
  assert.equal(h.get('input-panel').classList.contains('applied'),false);
  assert.equal(h.get('policy').textContent,'Both options enter the brain.');
});

test('a useful match remains visible through later empty searches',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  h.api.setEvidence(junction(),100);
  h.api.addDecision({...junction({applied:false,hits:false,rates:[30,30]}),time:200});
  h.api.tick(100);h.api.tick(180);
  assert.equal(h.get('junction-time').textContent,'Last memory use · 0.1 s');
  assert.equal(h.get('returned-count').textContent,'1');
  assert.equal(h.get('left-input').textContent,'0');
  assert.equal(h.api.state().elapsed,260);
});

test('offline playback preserves eight flies and labels recorded evidence in every stage',async()=>{
  const h=harness(true);await h.api.ready;
  for(const mode of ['none','personal','shared']){
    h.api.setMode(mode);await h.api.start();
    assert.equal(h.api.state().count,8);assert.equal(h.api.state().playing,true);
    assert.equal(h.get('playback-source').textContent,'Recorded fallback');
    assert.equal(h.get('spike-source').textContent,'Recorded spikes');
  }
  assert.equal(h.requests(),0);
});

test('historical inputs cannot appear continuously connected to current spikes',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  h.api.addFrame({ms:100,x:260,y:580,heading:0,left_input:0,right_input:30,neural:{ids:[]}});
  h.api.setEvidence(junction(),100);
  assert.equal(h.get('retrieval-flow').classList.contains('synchronized'),true);
  assert.equal(h.get('brain-time').textContent,'Now · 0.1 s');
  h.api.addFrame({ms:300,x:260,y:580,heading:0,left_input:30,right_input:30,neural:{ids:[]}});
  h.api.setEvidence(junction(),300);
  assert.equal(h.get('retrieval-flow').classList.contains('synchronized'),false);
  assert.equal(h.get('brain-time').textContent,'Now · 0.3 s');
  assert.equal(h.get('junction-time').textContent,'Last memory use · 0.1 s');
  assert.equal(h.get('left-input').textContent,'0');
});

test('all eight actors use fly artwork and the selected fly is larger',async()=>{
  const h=harness();await h.api.ready;await h.api.start();h.specimens.length=0;
  h.api.drawWorld();
  assert.equal(h.specimens.length,8);
  assert.equal(h.specimens.filter(f=>f.size===25).length,7);
  assert.equal(h.specimens.at(-1).size,32);
});
test('camera-oriented captures rotate into the maze coordinate frame',async()=>{
  const h=harness();await h.api.ready;
  for(const [bearing,expected] of [[0,Math.PI/2],[Math.PI/2,Math.PI],[Math.PI,-Math.PI/2],[-Math.PI/2,0]]){
    assert.ok(Math.abs(h.api.viewRotation(bearing)-expected)<1e-10);
  }
  h.api.imageInto('current-view','original-capture',false,0);
  const image=h.get('current-view').children[0];
  assert.equal(image.src,'original-capture');
  assert.equal(image.style.transform,`rotate(${Math.PI/2}rad)`);
});
test('Replay skips a non-candidate exclusion and targets changed sensory input',async()=>{
  const h=harness();await h.api.ready;h.api.setMode('personal');await h.api.start();
  const unrelated=junction({applied:false,rates:[30,30]});unrelated.views.push({...junction().views[0]});
  h.api.setEvidence(unrelated,300);
  assert.equal(h.get('replay-memory').hidden,true);
  h.api.addDecision({...junction(),time:200});
  h.api.replayMemory();assert.equal(h.api.state().elapsed,200);
  assert.equal(h.get('left-input').textContent,'0');
});
test('responsive presentation retains error visibility and named glyphs',()=>{
  const css=fs.readFileSync('_internal/maze/static/style.css','utf8');
  assert.doesNotMatch(css,/#message\s*\{[^}]*display\s*:\s*none/);
  const html=fs.readFileSync('_internal/maze/static/index.html','utf8');
  for(const id of ['turn','decision-choice'])assert.match(html,new RegExp(`id="${id}"[^>]*role="img"`));
});

test('offline playback cannot be mislabeled or blocked by the live steering control',async()=>{
  const h=harness(true);await h.api.ready;await h.api.start();
  assert.equal(h.get('disconnect').hidden,true);assert.equal(h.get('disconnect').disabled,true);
  await h.api.toggleSteering();
  assert.equal(h.api.state().disconnected,false);
  assert.equal(h.get('playback-source').textContent,'Recorded fallback');
  h.api.setMode('shared');await h.api.start();
  assert.equal(h.api.state().playing,true);
  assert.equal(h.get('playback-source').textContent,'Recorded fallback');
});
test('a failed steering request preserves the connected run and restores the toggle',async()=>{
  const h=harness();await h.api.ready;await h.api.start();h.setFail(true);
  await h.api.toggleSteering();
  assert.equal(h.api.state().disconnected,false);assert.equal(h.api.state().bundleDisconnected,false);
  assert.equal(h.get('playback-source').textContent,'Computed now');
  assert.equal(h.get('turn').textContent,'↑');
  assert.match(h.get('message').textContent,/Deliberate request failure/);
  h.setFail(false);h.api.setMode('shared');await h.api.start();
  assert.equal(h.api.state().playing,true);
});

test('disconnect and restore preserve the declared no-memory seed group',async()=>{
  const h=harness();await h.api.ready;await h.api.start();const seed=h.api.state().seed;
  await h.api.toggleSteering();await h.api.toggleSteering();
  assert.equal(h.api.state().seed,seed);
  assert.deepEqual(h.sentSeeds,[seed,seed,seed]);
});
test('only an explicit successful New group changes the comparison seed',async()=>{
  const h=harness();await h.api.ready;await h.api.start();const seed=h.api.state().seed;
  h.setFail(true);await h.api.start({newGroup:true});
  assert.equal(h.api.state().seed,seed);
  h.setFail(false);h.api.setMode('personal');await h.api.start();
  assert.equal(h.sentSeeds.at(-1),seed);
  h.api.setMode('none');await h.api.start({newGroup:true});
  assert.equal(h.api.state().seed,345678);
  assert.equal(h.sentSeeds.at(-1),345678);
});
