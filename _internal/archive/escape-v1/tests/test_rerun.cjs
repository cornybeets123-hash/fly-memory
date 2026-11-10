const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function harness(){
 const noop=()=>{};
 const graphics=new Proxy({}, {get:(o,k)=>k in o?o[k]:noop});
 class Element {
  constructor(id){this.id=id;this.disabled=false;this.style={};this.dataset={};this.classList={toggle:noop};}
  getBoundingClientRect(){return {width:400,height:220};}
  getContext(){return graphics;}
  addEventListener(){} replaceChildren(){} append(){} showModal(){} close(){}
 }
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);};
 const stages=['none','personal','shared'].map(mode=>{const e=new Element(mode);e.dataset.mode=mode;return e;});
 const document={getElementById:get,querySelectorAll:()=>stages,createElement:()=>new Element('new'),addEventListener:noop,documentElement:{requestFullscreen:noop}};
 let requests=0,fail=false,deferred=null;
 function run(mode){return {mode,index:{},brain:{protocol:'test'},observations:[],events:Array.from({length:6},(_,cycle)=>({cycle,fly:'A',cue:[1,0,0,0,0,0,0,0],hits:[],candidates:[],sweep:[1,3,5].includes(cycle),lead_ms:30,action_ms:null,selected_recording:null,neural:{trace:[],first_motor_ms:null},safe_feeding_ms:300,injuries:0,alive:true}))};}
 const fetch=async(url,options)=>{
  if(url.includes('positions'))return {ok:true,arrayBuffer:async()=>new Float32Array([0,0,1,1]).buffer};
  if(url.includes('groups'))return {ok:true,json:async()=>({groups:{}})};
  if(url.includes('status'))return {ok:true,json:async()=>({code:'test'})};
  requests++;if(fail)throw Error('Deliberate request failure');
  if(deferred)await new Promise(resolve=>deferred=resolve);
  const {mode}=JSON.parse(options.body);
  return {ok:true,json:async()=>({runs:mode==='none'?[run('none')]:[run('none'),run(mode)]})};
 };
 const window={devicePixelRatio:1,matchMedia:()=>({matches:false}),addEventListener:noop};
 const context=vm.createContext({window,document,fetch,requestAnimationFrame:noop,drawSpecimen:noop,console});
 vm.runInContext(fs.readFileSync('_internal/escape/static/app.js','utf8')+'\nglobalThis.api={start,setMode:v=>mode=v,state:()=>({busy,playing,mode,cycle}),ready:geometryReady};',context);
 return {context,get,requests:()=>requests,setFail:v=>fail=v,defer:()=>deferred=true,release:()=>{const done=deferred;deferred=null;done();}};
}
for(const mode of ['none','personal','shared'])test(`${mode}: repeated runs, busy guard, and error recovery`,async()=>{
 const h=harness(),api=h.context.api;await api.ready;api.setMode(mode);
 await api.start();assert.equal(h.get('run').disabled,false);assert.equal(api.state().busy,false);
 await api.start();assert.equal(h.requests(),2);assert.equal(api.state().mode,mode);
 h.defer();const pending=api.start();await Promise.resolve();await api.start();assert.equal(h.requests(),3);h.release();await pending;
 h.setFail(true);await api.start();assert.equal(h.get('run').disabled,false);assert.match(h.get('message').textContent,/Deliberate request failure/);
 h.setFail(false);await api.start();assert.equal(api.state().busy,false);assert.equal(h.get('run').disabled,false);
});
