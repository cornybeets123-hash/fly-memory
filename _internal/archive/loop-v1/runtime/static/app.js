/* One verified event log drives the maze, retrieved images, and neural activity. */
const $ = id => document.getElementById(id);
const COLORS = {mint:'#8ce5c0',pink:'#ff527d',purple:'#b49aff',blue:'#83ccff',muted:'#b7b4ca',white:'#f5f2fa'};
const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
let mode='none', bundle=null, world=null, busy=false, playing=false, elapsed=0, lastTime=0, speed=2;
let disconnected=false, heldUntil=0, milestones=new Set(), completed=new Set();
let positions=null, brainBackground=null, projectNeuron=null, lastEvidence='';
const playbackSource=window.WORKSHOP_DATA?'Recorded fallback':'Computed now';

function canvas(id){
  const element=$(id), box=element.getBoundingClientRect(), dpr=Math.min(window.devicePixelRatio||1,2);
  const width=Math.max(1,Math.round(box.width*dpr)),height=Math.max(1,Math.round(box.height*dpr));
  if(element.width!==width||element.height!==height){element.width=width;element.height=height;}
  const g=element.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);
  g.clearRect(0,0,box.width,box.height);
  return {g,w:box.width,h:box.height,dpr};
}
function label(g,value,x,y,size=14,color=COLORS.muted,align='left'){
  g.fillStyle=color;g.font=`${size>20?650:500} ${size}px Mona,system-ui`;g.textAlign=align;g.fillText(value,x,y);
}
function frameAt(run,time){
  if(!run?.frames.length)return null;
  let lo=0,hi=run.frames.length-1;
  while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(run.frames[mid].ms<=time)lo=mid;else hi=mid-1;}
  return run.frames[lo];
}
function latestDecision(){return bundle?.hero.decisions.findLast(d=>d.time<=elapsed);}
function currentMemories(){
  if(!bundle)return [];
  return [...bundle.initial_memories,...bundle.hero.observations.filter(o=>{
    const event=bundle.hero.events.find(e=>e.kind==='observed'&&e.snapshot===o.payload.snapshot&&e.observed_at_ms===o.payload.observed_at_ms);
    return event&&event.time<=elapsed;
  })];
}
function imageInto(id,url,matched=false){
  const target=$(id);target.classList.toggle('matched',matched);
  if(url){const img=document.createElement('img');img.src=url;img.alt=id==='current-view'?'The current visible entrance.':'The entrance from a completed observation.';target.replaceChildren(img);}
  else {const empty=document.createElement('span');empty.textContent='?';target.replaceChildren(empty);}
}
function evidence(){
  if(!bundle)return;
  const decision=latestDecision();
  const observation=bundle.hero.events.findLast(e=>e.kind==='observed'&&e.outcome==='returned'&&e.time<=elapsed);
  const showObservation=observation&&(!decision||observation.time>decision.time);
  const signature=`${mode}:${decision?.time}:${showObservation?observation.time:''}`;
  $('memory-count').textContent=mode==='none'?'Memory off':mode==='personal'?"A’s own experience":'A shared with B';
  if(signature===lastEvidence)return;
  lastEvidence=signature;
  if(showObservation){
    $('current-caption').textContent='Entrance view';$('stored-caption').textContent='Observed experience';
    const stored=currentMemories().find(o=>o.payload.snapshot===observation.snapshot);
    imageInto('current-view',stored?.image_url);imageInto('stored-view',stored?.image_url);
    $('memory-title').textContent=mode==='none'?'Back at start. Again.':'A completes its first loop.';
    $('evidence-result').textContent=mode==='none'?'It repeats the same choice.':'A stores its own observation.';
    $('evidence-result').classList.remove('hit');
    $('provenance').textContent=`Observed by ${observation.source_fly} during this run.`;
    return;
  }
  $('current-caption').textContent='Current view';$('stored-caption').textContent='From memory';
  if(!decision){
    imageInto('current-view',null);imageInto('stored-view',null);
    $('memory-title').textContent=mode==='shared'?'B starts with A’s experience.':mode==='personal'?'A starts with empty memory.':'Memory is off.';
    $('evidence-result').textContent=mode==='none'?'Every visit is a fresh choice.':mode==='personal'?'It must learn by exploring.':'B has never taken the loop.';
    $('provenance').textContent='';$('evidence-result').classList.remove('hit');return;
  }
  const matched=decision.views.find(v=>v.selected), view=matched||decision.views[decision.choice];
  imageInto('current-view',view.image_url,!!matched);
  const record=matched&&currentMemories().find(o=>o.payload.snapshot===matched.selected.payload.snapshot);
  imageInto('stored-view',record?.image_url,!!matched);
  $('memory-title').textContent=matched?(mode==='shared'?'A remembers. B benefits.':'A recognizes its own view.'):mode==='none'?'Same rule. Same choice.':'No experience yet.';
  $('evidence-result').textContent=matched?'Avoid the completed loop.':mode==='none'?(decision===bundle.hero.decisions[0]?'It takes the loop.':'It takes the loop again.'):'A explores before it can learn.';
  $('evidence-result').classList.toggle('hit',!!matched);
  $('provenance').textContent=matched?`Observed by ${matched.selected.payload.source_fly}. ${matched.applied?`Used by ${bundle.hero.owner}.`:'Not applied.'}`:'';
}

function drawWorld(){
  const {g,w,h}=canvas('world');if(!world)return;
  const [x0,y0,x1,y1]=world.bounds,pad=44,scale=Math.min((w-pad*2)/(x1-x0),(h-pad*2)/(y1-y0));
  const ox=(w-(x1-x0)*scale)/2-x0*scale,oy=(h-(y1-y0)*scale)/2-y0*scale;
  const point=(x,y)=>[ox+x*scale,oy+y*scale];
  g.save();g.translate(ox,oy);g.scale(scale,scale);
  g.shadowColor='#03040b99';g.shadowBlur=20/scale;g.shadowOffsetY=8/scale;
  g.beginPath();for(const [a,b,c,d] of world.rectangles)g.rect(a,c,b-a,d-c);
  g.fillStyle='#ded8c1';g.fill();g.shadowBlur=0;g.shadowOffsetY=0;
  g.lineWidth=3/scale;g.strokeStyle='#8a91a4';g.lineCap='round';
  g.beginPath();for(const [a,b,c,d] of world.walls){g.moveTo(a,b);g.lineTo(c,d);}g.stroke();
  for(const [x,y,color,radius] of world.landmarks){
    g.fillStyle=`rgb(${color.join(',')})`;g.beginPath();g.arc(x,y,radius,0,Math.PI*2);g.fill();
    g.strokeStyle='#ffffff25';g.lineWidth=1.2/scale;
    for(const a of [0,1.8,3.9]){g.beginPath();g.ellipse(x+Math.cos(a)*radius*.3,y+Math.sin(a)*radius*.3,radius*.6,radius*.25,a,0,Math.PI*2);g.stroke();}
  }
  g.restore();
  const heroColor=mode==='shared'?COLORS.pink:COLORS.mint;
  const [ex,ey]=point(...world.exit);
  g.fillStyle='#07352d';g.strokeStyle=COLORS.mint;g.lineWidth=1.5;
  g.beginPath();g.roundRect(ex-31,ey-15,62,30,5);g.fill();g.stroke();label(g,'EXIT',ex,ey+5,15,COLORS.mint,'center');
  const [sx,sy]=point(world.start[0],world.start[1]);
  g.strokeStyle='#ffffff77';g.lineWidth=2;g.beginPath();g.moveTo(sx-27*scale,sy);g.lineTo(sx+27*scale,sy);g.stroke();
  label(g,'START',sx,sy+35,13,COLORS.muted,'center');
  const [lx,ly]=point(150,430);label(g,'LOOP',lx,ly,19,COLORS.muted,'center');
  function trail(run,color,ghost){
    if(!run)return;
    g.beginPath();let started=false;
    for(let i=0;i<run.frames.length;i+=5){const f=run.frames[i];if(f.ms>elapsed)break;const [x,y]=point(f.x,f.y);if(!started){g.moveTo(x,y);started=true;}else g.lineTo(x,y);}
    g.lineWidth=ghost?2:3;g.strokeStyle=color;g.globalAlpha=ghost?.35:.85;g.setLineDash(ghost?[4,6]:[]);g.stroke();g.setLineDash([]);g.globalAlpha=1;
  }
  trail(bundle?.ghost,'#7e7b94',true);trail(bundle?.hero,heroColor,false);
  function actor(frame,ghost=false){
    if(!frame)return;const [x,y]=point(frame.x,frame.y);g.save();g.translate(x,y);
    if(ghost){g.globalAlpha=.42;g.strokeStyle='#aaa8c4';g.lineWidth=1.5;g.beginPath();g.arc(0,0,13,0,Math.PI*2);g.stroke();g.rotate(frame.heading);g.beginPath();g.moveTo(13,0);g.lineTo(5,-4);g.lineTo(5,4);g.closePath();g.fillStyle='#d4d0e8';g.fill();}
    else {g.shadowColor=heroColor;g.shadowBlur=17;g.fillStyle='#151627';g.strokeStyle=heroColor;g.lineWidth=2;g.beginPath();g.arc(0,0,19,0,Math.PI*2);g.fill();g.stroke();g.shadowBlur=0;if(typeof drawSpecimen==='function')drawSpecimen(g,19,frame.heading,reducedMotion?0:elapsed*.009,heroColor);}
    g.restore();
  }
  actor(frameAt(bundle?.ghost,elapsed),true);
  actor(frameAt(bundle?.hero,elapsed)||{x:world.start[0],y:world.start[1],heading:world.start[2]});
  const decision=latestDecision();
  if(decision&&elapsed-decision.time<2500){
    const f=frameAt(bundle.hero,decision.time), [x,y]=point(f.x,f.y);
    for(const v of decision.views){
      const a=f.heading+v.bearing,used=v.selected&&v.applied;
      if(!used&&v!==decision.views[decision.choice])continue;
      const [tx,ty]=point(f.x+Math.cos(a)*65,f.y+Math.sin(a)*65);
      g.strokeStyle=used?COLORS.pink:COLORS.mint;g.lineWidth=2;g.beginPath();g.moveTo(x,y);g.lineTo(tx,ty);g.stroke();
      if(used){g.lineWidth=3;g.beginPath();g.moveTo(tx-5,ty-5);g.lineTo(tx+5,ty+5);g.moveTo(tx-5,ty+5);g.lineTo(tx+5,ty-5);g.stroke();}
      else {g.fillStyle=COLORS.mint;g.save();g.translate(tx,ty);g.rotate(a);g.beginPath();g.moveTo(7,0);g.lineTo(-5,-5);g.lineTo(-5,5);g.closePath();g.fill();g.restore();}
    }
  }
}

function prepareBrain(){
  if(!positions)return;const {w,h,dpr}=canvas('brain');
  const xs=[],ys=[];for(let i=0;i<positions.length;i+=2){if(Number.isFinite(positions[i])&&Number.isFinite(positions[i+1])){xs.push(positions[i]);ys.push(positions[i+1]);}}
  xs.sort((a,b)=>a-b);ys.sort((a,b)=>a-b);
  const loX=xs[Math.floor(xs.length*.001)],hiX=xs[Math.floor(xs.length*.999)],loY=ys[Math.floor(ys.length*.001)],hiY=ys[Math.floor(ys.length*.999)];
  const scale=Math.min((w-14)/(hiX-loX),(h-12)/(hiY-loY));
  projectNeuron=i=>[(positions[i*2]-(loX+hiX)/2)*scale+w/2,((loY+hiY)/2-positions[i*2+1])*scale+h/2];
  brainBackground=document.createElement('canvas');brainBackground.width=Math.round(w*dpr);brainBackground.height=Math.round(h*dpr);
  const g=brainBackground.getContext('2d');g.scale(dpr,dpr);g.fillStyle='#8c83bd';g.globalAlpha=.12;
  for(let i=0;i<positions.length/2;i++){const [x,y]=projectNeuron(i);g.fillRect(x,y,.65,.65);}
}
function drawBrain(){
  const {g,w,h}=canvas('brain');if(brainBackground)g.drawImage(brainBackground,0,0,w,h);
  const current=frameAt(bundle?.hero,elapsed);
  if(bundle&&projectNeuron){
    const frames=bundle.hero.frames;
    for(let i=Math.max(0,Math.floor(elapsed/20)-5);i<frames.length&&i<=Math.floor(elapsed/20);i++){
      const f=frames[i];if(f.ms>elapsed||f.ms<elapsed-100)continue;
      g.globalAlpha=Math.max(.1,1-(elapsed-f.ms)/120);g.fillStyle=COLORS.mint;
      for(const id of f.neural.ids){const [x,y]=projectNeuron(id);g.fillRect(x-1,y-1,2,2);}
    }
    g.globalAlpha=1;
    for(const [side,color] of [['left',COLORS.purple],['right',COLORS.pink]]){
      const count=current?.neural[side]||0;g.strokeStyle=color;g.fillStyle=color;
      for(const id of bundle.brain.readout[side]){const [x,y]=projectNeuron(id);g.beginPath();g.arc(x,y,count?3.5:2,0,Math.PI*2);if(count)g.fill();else g.stroke();}
    }
  }
  const neural=current?.neural;
  $('left-bar').style.width=`${Math.min(100,(neural?.rateL||0)/4)}%`;
  $('right-bar').style.width=`${Math.min(100,(neural?.rateR||0)/4)}%`;
  $('turn').textContent=disconnected?'Disconnected':(current?.applied_yaw||0)<-.08?'Left':(current?.applied_yaw||0)>.08?'Right':'Straight';
  $('input').textContent=`LC10a input: ${Math.round(current?.left_input||0)} / ${Math.round(current?.right_input||0)} Hz`;
}
function update(){
  drawWorld();drawBrain();evidence();
  $('timer').replaceChildren(document.createTextNode((elapsed/1000).toFixed(1)),Object.assign(document.createElement('span'),{textContent:'s'}));
  if(!bundle)return;
  const done=elapsed>=bundle.hero.summary.time_ms;
  $('result').textContent=done?(bundle.hero.summary.exit?`Exit found in ${(bundle.hero.summary.time_ms/1000).toFixed(1)} s`:`${bundle.hero.summary.returns} loops. No exit in 45 s.`):'';
  const d=latestDecision(),terminal=bundle.hero.events.findLast(e=>e.kind==='observed'&&e.outcome==='returned'&&e.time<=elapsed);
  $('scene-caption').textContent=terminal&&elapsed-terminal.time<1800?mode==='none'?'Back at start. The next choice repeats.':'Back at start. A stores this experience.':d&&elapsed-d.time<2300?(d.views.some(v=>v.selected)?mode==='shared'?'B uses A’s memory on its first visit.':'A uses its own memory on its second visit.':mode==='none'?'No experience guides the choice.':'No matching memory. It explores.') :'';
  $('pause').textContent=playing?'Pause':'Resume';
}
function milestonesFor(run){return [...run.decisions.map(d=>({time:d.time,key:`q${d.time}`,hold:d.views.some(v=>v.selected)?1800:700})),...run.events.filter(e=>e.kind==='observed'&&e.outcome==='returned').map(e=>({time:e.time,key:`o${e.time}`,hold:1800}))].sort((a,b)=>a.time-b.time);}
function tick(time){
  if(playing&&bundle){
    const delta=lastTime?Math.min(80,time-lastTime):0;lastTime=time;
    if(time>=heldUntil){
      const end=Math.max(bundle.hero.summary.time_ms,bundle.ghost?.summary.time_ms||0),next=Math.min(end,elapsed+delta*speed);
      const event=milestonesFor(bundle.hero).find(e=>e.time>elapsed&&e.time<=next&&!milestones.has(e.key));
      if(event){elapsed=event.time;milestones.add(event.key);heldUntil=time+(reducedMotion?0:event.hold);}
      else elapsed=next;
      if(elapsed>=end){playing=false;$('pause').disabled=true;completed.add(mode);$('message').textContent=mode==='none'?'Build personal memory in memory.py.':mode==='personal'?'Share the observed experience in pipeline.py.':'The newcomer used another fly’s experience.';}
    }
    update();
  }
  requestAnimationFrame(tick);
}
function selectStage(next){
  if(busy)return;
  if(next==='personal'&&!completed.has('none')){$('message').textContent='Watch the first attempt before adding memory.';return;}
  if(next==='shared'&&!completed.has('personal')){$('message').textContent='Watch the personal-memory attempt before sharing.';return;}
  mode=next;for(const button of document.querySelectorAll('.stage')){const selected=button.dataset.mode===mode;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));}
  start();
}
async function start(){
  if(busy)return;
  busy=true;playing=false;$('run').disabled=true;$('pause').disabled=true;$('computing').hidden=false;
  for(const button of document.querySelectorAll('.stage'))button.disabled=true;
  $('message').textContent=window.WORKSHOP_DATA?'Loading the recorded run.':'Computing the brain and querying Qdrant…';
  try{
    await ready;
    let data;
    if(window.WORKSHOP_DATA){data=window.WORKSHOP_DATA.runs[`${mode}:${disconnected?'mute':'normal'}`];if(!data)throw Error('This control is available in the live workshop.');}
    else {const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,seed:2000,disconnect:disconnected})});const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'The run request failed.');data=result;}
    bundle=data;world=data.world;elapsed=0;heldUntil=0;milestones=new Set();lastEvidence='';lastTime=0;playing=true;
    $('hero-name').textContent=mode==='shared'?'Fly B':'Fly A';$('ghost-key').hidden=!data.ghost;
    $('ghost-key').replaceChildren(Object.assign(document.createElement('i'),{className:'ghost-dot'}),document.createTextNode(mode==='shared'?' B with personal memory':' A without memory'));
    document.body.dataset.mode=mode;
    $('chapter').textContent=mode==='none'?'THE FIRST ATTEMPT':mode==='personal'?'EMPTY MEMORY AT THE START':'A NEW FLY, WITH SHARED EXPERIENCE';
    $('headline').textContent=mode==='none'?'It keeps taking the loop.':mode==='personal'?'A learns during this run.':'B skips A’s mistake.';
    $('message').textContent=`${playbackSource}. ${speed}× playback. Actual spikes and query results.`;
    $('run').textContent='Run again';$('pause').disabled=false;update();
  }catch(error){$('message').textContent=error.message;}
  finally{busy=false;$('run').disabled=false;$('computing').hidden=true;for(const button of document.querySelectorAll('.stage'))button.disabled=false;}
}
const ready=(async()=>{
  if(window.WORKSHOP_DATA){const bytes=Uint8Array.from(atob(window.WORKSHOP_DATA.positions_b64),c=>c.charCodeAt(0));positions=new Float32Array(bytes.buffer);world=window.WORKSHOP_DATA.world;}
  else {const responses=await Promise.all([fetch('/assets/brain-positions.bin'),fetch('/api/status')]);if(responses.some(r=>!r.ok))throw Error('The display could not load. Restart the workshop.');positions=new Float32Array(await responses[0].arrayBuffer());world=(await responses[1].json()).world;}
  prepareBrain();update();
})();
ready.catch(error=>$('message').textContent=error.message);
$('run').addEventListener('click',start);
for(const button of document.querySelectorAll('.stage'))button.addEventListener('click',()=>selectStage(button.dataset.mode));
$('pause').addEventListener('click',()=>{if(!bundle)return;playing=!playing;lastTime=0;update();});
$('speed').addEventListener('click',()=>{speed=speed===2?1:speed===1?4:2;$('speed').textContent=`${speed}× playback`;});
$('disconnect').addEventListener('click',()=>{if(busy)return;disconnected=!disconnected;$('disconnect').setAttribute('aria-pressed',String(disconnected));if(bundle)start();});
$('fullscreen').addEventListener('click',()=>{const request=document.documentElement.requestFullscreen?.();request?.catch?.(()=>$('message').textContent='Use the browser’s full-screen control.');});
$('inspect').addEventListener('click',()=>{$('details').textContent=JSON.stringify(bundle?{source:playbackSource,mode,seed:bundle.hero.seed,summary:bundle.hero.summary,comparison:bundle.ghost?.summary,current_decision:latestDecision(),neural_frame:frameAt(bundle.hero,elapsed),memory_protocol:bundle.initial_memories[0]?.payload.protocol} :{status:'Run the demo to inspect its evidence.'},null,2);$('inspector').showModal();});
$('close-inspector').addEventListener('click',()=>$('inspector').close());
window.addEventListener('resize',()=>{prepareBrain();update();});
document.addEventListener('keydown',event=>{if(['INPUT','TEXTAREA'].includes(event.target.tagName)||$('inspector').open)return;if(event.code==='Space'){event.preventDefault();$('pause').click();}else if(event.key==='r')start();else if(['1','2','3'].includes(event.key))selectStage(['none','personal','shared'][Number(event.key)-1]);});
requestAnimationFrame(tick);
