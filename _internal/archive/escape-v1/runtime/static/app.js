/* One event log drives the arena, real neural spikes, and actual retrieval results. */
const $ = id => document.getElementById(id);
const C = {pink:'#ff3d81',cyan:'#72e8ef',white:'#eef1ff',muted:'#95a2cc',green:'#a8f2c5'};
let mode='none', run=null, runs=[], cycle=0, ms=0, playing=false, busy=false, lastTime=0, hold=0;
let positions=null, groups=null, bg=null, projection=null, currentEvent=null;
let control='normal';
const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const canvases=['world','brain','raster','memoryMap'];
const geometryReady = (async()=>{
  if(window.WORKSHOP_DATA){const bytes=Uint8Array.from(atob(window.WORKSHOP_DATA.positions_b64),c=>c.charCodeAt(0));positions=new Float32Array(bytes.buffer);groups=window.WORKSHOP_DATA.groups;}
  else {
    const responses=await Promise.all([fetch('/static/brain-positions.bin'),fetch('/static/brain-groups.json')]);
    if(responses.some(r=>!r.ok))throw Error('The neural display assets could not load. Restart the workshop.');
    positions=new Float32Array(await responses[0].arrayBuffer());groups=await responses[1].json();
  }
  resize();
})();
function setup(canvas){
  const dpr=Math.min(window.devicePixelRatio||1,2),r=canvas.getBoundingClientRect();
  canvas.width=Math.max(1,Math.round(r.width*dpr));canvas.height=Math.max(1,Math.round(r.height*dpr));
  const g=canvas.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);return {g,w:r.width,h:r.height};
}
function resize(){
  for(const id of canvases)setup($(id));
  if(positions){
    const r=$('brain').getBoundingClientRect();
    const xs=[],ys=[];for(let i=0;i<positions.length;i+=2){if(Number.isFinite(positions[i])&&Number.isFinite(positions[i+1])){xs.push(positions[i]);ys.push(positions[i+1]);}}
    xs.sort((a,b)=>a-b);ys.sort((a,b)=>a-b);
    const loX=xs[Math.floor(xs.length*.001)],hiX=xs[Math.floor(xs.length*.999)];
    const loY=ys[Math.floor(ys.length*.001)],hiY=ys[Math.floor(ys.length*.999)];
    const scale=Math.min((r.width-25)/(hiX-loX),(r.height-30)/(hiY-loY));
    projection=i=>[(positions[2*i]-(loX+hiX)/2)*scale+r.width/2,((loY+hiY)/2-positions[2*i+1])*scale+r.height/2];
    bg=document.createElement('canvas');bg.width=$('brain').width;bg.height=$('brain').height;
    const b=bg.getContext('2d'),dpr=Math.min(window.devicePixelRatio||1,2);b.scale(dpr,dpr);
    b.fillStyle='#5d6c9b';b.globalAlpha=.10;
    for(let i=0;i<positions.length/2;i++){const [x,y]=projection(i);b.fillRect(x,y,.8,.8);}
  }
  draw();
}
window.addEventListener('resize',resize);
function clearCanvas(id){const c=$(id),g=c.getContext('2d'),r=c.getBoundingClientRect();g.clearRect(0,0,r.width,r.height);return {g,w:r.width,h:r.height};}
function text(g,s,x,y,size=14,color=C.muted,align='left'){g.fillStyle=color;g.font=`${size>=22?'650':'500'} ${size}px Mona,system-ui`;g.textAlign=align;g.fillText(s,x,y);}
function round(g,x,y,w,h,r=8){g.beginPath();g.roundRect(x,y,w,h,r);}
function eventAt(fly,at=cycle,source=run){return source?.events.find(e=>e.cycle===at&&e.fly===fly);}
function focused(){return eventAt('A');}
function visibleMemories(){
  if(!run||mode==='none')return [];
  return run.observations.filter(o=>o.payload.observed_cycle<cycle&&(o.scope==='A'||mode==='shared'));
}
function headline(){
  if(!run)return 'Can a memory save a fly?';
  const e=focused();if(!e)return 'The experiment is complete.';
  if(!e.sweep)return 'A similar cue. A quiet cycle.';
  if(cycle===3)return 'Clear view: the reflex has time.';
  if(mode==='shared')return 'A new fly. Shared experience.';
  if(mode==='personal')return 'It remembers the first encounter.';
  return cycle===5?'The same mistake. Again.':'The screen hides the approaching swatter.';
}
function updatePanels(){
  currentEvent=focused();$('headline').textContent=headline();
  const e=currentEvent;
  $('chapter').textContent=e?`SCENE ${cycle+1} / 6 · ${e.sweep?(e.lead_ms>=60?'CLEAR VIEW':'OCCLUDED APPROACH'):'SAFE LOOKALIKE'}`:'THE EXPERIMENT';
  $('brainTitle').textContent='Fly A: neural response';
  const memories=visibleMemories();$('pointCount').textContent=`${memories.length} memories`;
  $('matches').replaceChildren();
  const hits=e?[...e.hits].sort((a,b)=>b.score-a.score):[];
  const unique=[...new Map(hits.map(h=>[h.id,h])).values()].slice(0,3);
  if(!unique.length){
    $('memoryTitle').textContent=mode==='none'?'Experience leaves no trace.':'No eligible episode matches.';
    const d=document.createElement('div');d.className='empty';d.textContent=mode==='none'?'Nothing stored. Nothing recalled.':'The normal reflex stays active.';$('matches').append(d);
  }else{
    const selected=hits.find(h=>h.payload.recording===e.selected_recording);
    $('memoryTitle').textContent=selected?(selected.payload.sweep?'Recall brings the warning forward.':'The closest experience was quiet.'):'Conflicting evidence: use the reflex.';
    for(const h of unique){
      const d=document.createElement('div');d.className='match'+(h.payload.recording===e.selected_recording?' selected':'');
      const top=document.createElement('div');top.className='match-top';
      const name=document.createElement('span');name.textContent=h.payload.source_fly==='A'?'Fly A: observed experience':`${h.payload.source_fly}: observed experience`;
      const score=document.createElement('span');score.className='match-score';score.textContent=h.score.toFixed(4);top.append(name,score);
      const detail=document.createElement('div');detail.className='match-details';detail.textContent=`#${h.id} · ${h.payload.sweep?'Sweep observed':'Quiet cycle observed'} · ${h.payload.source_fly==='A'?'personal':'shared'}`;
      d.append(top,detail);$('matches').append(d);
    }
  }
  $('filterLabel').textContent=mode==='shared'?'Same arena. Same model. Other sources allowed.':'Same arena. Same model. Observed episodes.';
  $('pause').disabled=!run;$('next').disabled=!run;$('pause').textContent=playing?'Pause':'Play';
  $('queryDetails').textContent=JSON.stringify({
    engine:run?.index,query:e?.cue,using:'cue',limit:3,score_threshold:.98,
    filter:{arena:'orchard',protocol:run?.brain.protocol,shared_source_exclusion:mode==='shared'?'A':null},
    query_ms:e?.query_ms,returned:unique,selected_input_recording:e?.selected_recording,
    actual_unfiltered_candidates:e?.candidates,
    timing:{natural_looming_ms:e?200-e.lead_ms:null,dnp01_ms:e?.neural.first_motor_ms,refuge_clearance_ms:45,strike_ms:200},
  },null,2);
}
function drawWorld(){
  const {g,w,h}=clearCanvas('world'),e=focused(),t=run?ms:-1;
  const feed=h*.39,refuge=h*.79;
  // Fixed refuge geometry: movement takes 45 ms in the declared engineered actor.
  g.fillStyle='#18382f';round(g,35,refuge-24,w-70,50,13);g.fill();
  g.strokeStyle='#387d66';g.lineWidth=1;g.stroke();text(g,'REFUGE',w-52,refuge+5,12,C.green,'right');
  g.fillStyle='#313251';round(g,35,feed-23,w-70,47,12);g.fill();
  text(g,'FOOD',50,feed+4,11,'#d3bf8a');
  for(let i=0;i<6;i++){
    const x=110+(w-220)*i/5;
    g.fillStyle='#c6a968';g.beginPath();g.ellipse(x,feed,25,8,0,0,Math.PI*2);g.fill();
    g.strokeStyle='#6d687a';g.setLineDash([3,6]);g.beginPath();g.moveTo(x,feed+30);g.lineTo(x,refuge-28);g.stroke();g.setLineDash([]);
  }
  if(e?.sweep&&t>=0){
    const start=200-e.lead_ms,visible=t>=start;
    // The displayed cover hides the fixed approach until its sensory visibility time.
    if(e.lead_ms<60&&t<start){g.fillStyle='#252c4a';round(g,35,5,w-70,feed-58,8);g.fill();g.strokeStyle='#4c5675';g.stroke();text(g,'SCREEN',w/2,Math.max(23,(feed-50)/2),11,'#a5b1ce','center');}
    if(visible){
      const front=Math.min(feed+23,feed+(t-200)*1.55),height=Math.max(38,h*.22);
      g.save();g.fillStyle=t>=200?'#e72b5d':'#ae254e';g.strokeStyle='#ff7694';g.lineWidth=2;
      round(g,w*.78,front-height-55,17,60,6);g.fill();g.stroke();
      round(g,70,front-height,w-140,height,13);g.fill();g.stroke();
      g.globalAlpha=.65;g.lineWidth=1;g.strokeStyle='#ffd7df';
      for(let x=85;x<w-80;x+=21){g.beginPath();g.moveTo(x,front-height+8);g.lineTo(x,front-8);g.stroke();}
      for(let y=front-height+12;y<front-5;y+=14){g.beginPath();g.moveTo(80,y);g.lineTo(w-80,y);g.stroke();}
      g.restore();text(g,'SWATTER',w/2,front-height-7,11,'#ffb0c4','center');
    }
  }
  for(let i=0;i<6;i++){
    const fly=String.fromCharCode(65+i),ev=eventAt(fly),x=110+(w-220)*i/5;
    const prev=run?run.events.filter(v=>v.fly===fly&&v.cycle<cycle).at(-1):null;
    const wasDead=prev&&!prev.alive;
    let y=feed,flight=0;
    if(ev&&ev.action_ms!==null&&t>=ev.action_ms){const at=ev.hit?Math.min(t,200):t;flight=Math.max(0,Math.min(1,(at-ev.action_ms)/45));y=feed+(refuge-feed)*flight;}
    const hitNow=Boolean(ev?.hit&&t>=200),dead=wasDead||(hitNow&&!ev.alive);
    if(i===0){g.strokeStyle=ev?.selected_recording?C.pink:C.cyan;g.lineWidth=1.5;g.beginPath();g.ellipse(x,y,34,25,0,0,Math.PI*2);g.stroke();}
    g.save();g.translate(x,y-Math.sin(flight*Math.PI)*20);g.globalAlpha=dead?.30:1;
    if(hitNow&&!dead){g.shadowColor=C.pink;g.shadowBlur=14;}
    drawSpecimen(g,i===0?31:Math.max(14,Math.min(21,w/65)),-Math.PI/2,t*.08+i,C.cyan,dead);g.restore();
    if(t<45&&t>=0){g.strokeStyle=ev?.selected_recording?C.pink:'#cad8ef';g.globalAlpha=.7*(1-t/45);g.lineWidth=2;g.beginPath();g.arc(x,feed,28+t*.7,0,Math.PI*2);g.stroke();g.globalAlpha=1;}
    text(g,dead?'×':fly,x,refuge+48,14,dead?C.pink:C.muted,'center');
    if(ev&&t>=200)text(g,ev.hit?'HIT':ev.sweep?'CLEAR':'FED',x,y-35,12,ev.hit?C.pink:ev.sweep?C.green:C.white,'center');
    if(mode!=='none'&&ev?.sweep){
      const baseline=eventAt(fly,cycle,runs.find(r=>r.mode==='none'));
      if(baseline?.action_ms!==null&&t>=0){
        const f=t>=baseline.action_ms?Math.min(1,(t-baseline.action_ms)/45):0;
        g.save();g.translate(x+37,feed+(refuge-feed)*f);g.globalAlpha=.16;drawSpecimen(g,13,-Math.PI/2,0,'#fff',false);g.restore();
      }
    }
  }
  if(mode!=='none'&&e?.sweep)text(g,'Ghost: same run without memory',w/2,h-2,10,'#8b99bb','center');
}
function drawBrain(){
  const {g,w,h}=clearCanvas('brain');if(!bg||!projection)return;
  g.save();g.setTransform(1,0,0,1,0,0);g.drawImage(bg,0,0);g.restore();
  const e=focused(),frame=e?.neural.trace?.find(v=>v.ms===Math.floor(ms/5)*5);
  const active=new Set(frame?.ids||[]),sensory=new Set([...(groups?.groups.LPLC2_L||[]),...(groups?.groups.LPLC2_R||[]),...(groups?.groups.LC4_L||[]),...(groups?.groups.LC4_R||[])]);
  g.globalAlpha=.8;g.fillStyle=C.cyan;
  for(const i of active){const [x,y]=projection(i);if(x<0||y<0||x>w||y>h)continue;g.beginPath();g.arc(x,y,sensory.has(i)?1.8:1.3,0,Math.PI*2);g.fill();}
  g.globalAlpha=1;
  const motor=e?.neural.first_motor_ms;
  const firing=motor!==null&&motor!==undefined&&ms>=motor;
  for(const id of [...(groups?.groups.DNp01_L||[]),...(groups?.groups.DNp01_R||[])]){
    const [x,y]=projection(id);g.strokeStyle=firing?C.pink:'#7680a7';g.lineWidth=2;g.fillStyle=firing?C.pink:'#161f3b';g.beginPath();g.arc(x,y,firing?7:4,0,Math.PI*2);g.fill();g.stroke();
    if(firing){g.globalAlpha=.18;g.beginPath();g.arc(x,y,16,0,Math.PI*2);g.fill();g.globalAlpha=1;}
  }
  $('motorState').style.color=firing?C.pink:C.white;
  $('motorTime').textContent=firing?`Fired at ${motor.toFixed(1)} ms`:e?.selected_recording?'Recorded inputs replay':'Waiting for looming';
  const seen=new Set((e?.neural.trace||[]).filter(f=>f.ms<=ms).flatMap(f=>f.ids));
  $('activeCount').textContent=`${seen.size.toLocaleString()} neurons active so far`;
  const r=clearCanvas('raster'),tr=e?.neural.trace||[];
  for(let row=0;row<2;row++){r.g.strokeStyle='#354062';r.g.beginPath();r.g.moveTo(0,18+row*28);r.g.lineTo(r.w,18+row*28);r.g.stroke();}
  for(const f of tr){if(f.ms>ms||f.ms>300)continue;const x=f.ms/300*r.w;r.g.fillStyle=C.white;r.g.fillRect(x,18-Math.min(15,f.input*.22),2,Math.min(15,f.input*.22));r.g.fillStyle=C.pink;r.g.fillRect(x,46-Math.min(22,f.motor*5),2,Math.min(22,f.motor*5));}
  text(r.g,'Input',2,13,9,C.muted);text(r.g,'DNp01',2,62,9,C.muted);
}
function drawMemory(){
  const {g,w,h}=clearCanvas('memoryMap'),e=focused();
  const hits=e?[...new Map([...e.hits].sort((a,b)=>b.score-a.score).map(v=>[v.id,v])).values()].slice(0,3):[];
  const qx=w*.20,qy=h*.47;
  if(!e){text(g,'Stored experience',w/2,h/2,13,C.muted,'center');return;}
  for(let i=0;i<hits.length;i++){
    const hit=hits[i],x=w*.76,y=h*(.19+i*.29),selected=hit.payload.recording===e.selected_recording;
    g.strokeStyle=selected?C.pink:'#52618c';g.lineWidth=selected?2.5:1;
    g.beginPath();g.moveTo(qx+18,qy);g.bezierCurveTo(w*.48,qy,w*.46,y,x-19,y);g.stroke();
    g.fillStyle=selected?'#452241':'#1d294b';g.beginPath();g.arc(x,y,19,0,Math.PI*2);g.fill();g.stroke();
    text(g,`#${hit.id}`,x,y+4,10,selected?C.pink:C.white,'center');
  }
  g.fillStyle='#192743';g.strokeStyle=C.white;g.lineWidth=2;g.beginPath();g.arc(qx,qy,18,0,Math.PI*2);g.fill();g.stroke();
  text(g,mode==='none'?'CUE':'QUERY',qx,qy+37,10,C.white,'center');
  if(!hits.length){g.setLineDash([3,5]);g.strokeStyle='#405071';g.beginPath();g.moveTo(qx+23,qy);g.lineTo(w*.78,qy);g.stroke();g.setLineDash([]);text(g,'∅',w*.80,qy+8,24,C.muted,'center');}
  for(let i=0;i<8;i++){const value=e.cue[i];g.fillStyle=i===0?C.cyan:'#637aa7';g.fillRect(qx-24+i*6,h-20,4,-Math.abs(value)*22);}
}
function updateMetrics(){
  if(!run)return;
  const complete=run.events.filter(e=>e.cycle<cycle||(e.cycle===cycle&&ms>=200));
  const injuries={};for(const e of complete)injuries[e.fly]=e.injuries;
  $('survivors').textContent=`${6-Object.values(injuries).filter(n=>n>=2).length}/6`;
  $('harm').textContent=complete.filter(e=>e.hit).length;
  const safe=complete.filter(e=>!e.sweep),sum=safe.reduce((v,e)=>v+e.safe_feeding_ms,0);
  $('feeding').textContent=safe.length?`${Math.round(sum/(safe.length*300)*100)}%`:'100%';
  const e=focused();
  $('outcome').textContent=!e?'Experiment complete.':ms<200?(e.selected_recording?'Retrieved input reaches the brain early.':'The fly relies on current sensory input.'):(e.hit?'Too late. The fly did not clear the footprint.':e.sweep?'DNp01 fired. The fly reached the refuge.':e.false_jump?'The fly escaped a quiet cue and lost feeding time.':'The fly keeps feeding. No false escape.');
  $('clock').textContent=`${Math.round(ms)} ms`;$('seek').value=ms;
}
function draw(){drawWorld();drawBrain();drawMemory();updateMetrics();}
function moveScene(next){
  if(!run)return;cycle=Math.min(5,Math.max(0,next));ms=0;hold=0;lastTime=0;updatePanels();draw();
}
function tick(now){
  const delta=lastTime?Math.min(now-lastTime,80):0;lastTime=now;
  if(playing&&run){
    if(ms<350)ms=Math.min(350,ms+delta/20);
    else{hold+=delta;if(hold>1000){if(cycle<5)moveScene(cycle+1);else{playing=false;$('pause').textContent='Play';$('run').innerHTML='Run again <span>↗</span>';$('message').textContent='Same world and seeds. Change the memory stage to compare.';}}}
    draw();
  }
  requestAnimationFrame(tick);
}
async function start(nextControl='normal',targetCycle=null){
  if(busy)return;busy=true;playing=false;$('run').disabled=true;$('message').textContent='Computing neural responses and querying Qdrant locally…';
  try{
    await geometryReady;
    let data;
    if(window.WORKSHOP_DATA){const selected=nextControl==='normal'?window.WORKSHOP_DATA.runs.find(r=>r.mode===mode):window.WORKSHOP_DATA.controls[`${mode}:${nextControl}`];data={runs:[window.WORKSHOP_DATA.runs.find(r=>r.mode==='none'),selected].filter(Boolean)};}
    else{const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,seed:2000,control:nextControl})});data=await response.json();if(!response.ok)throw Error(data.detail||'The experiment failed.');}
    runs=data.runs;run=runs.find(r=>r.mode===mode);if(!run)throw Error('This memory stage is unavailable.');
    control=nextControl;cycle=targetCycle??(mode==='personal'?5:1);ms=0;hold=0;lastTime=0;playing=!reduced;
    $('message').textContent=mode==='personal'?'Earlier scenes include the first encounter for Fly A. This is the matched repeat.':mode==='shared'?'Fresh recipients start with empty personal memory. Scout observed two earlier cycles.':'';
    $('runtimeLabel').textContent=`${window.WORKSHOP_DATA?'Recorded computed run':'Live neural computation'} · Engineered arena · 20× slower playback`;
    if(control!=='normal')$('message').textContent=control==='no_replay'?'RECALL MUTED. Retrieval still runs. Recorded inputs cannot enter the brain.':'ESCAPE READOUT DISABLED. Neural spikes remain. The body cannot escape.';
    updatePanels();draw();
  }catch(error){$('message').textContent=error.message;}
  finally{busy=false;$('run').disabled=false;$('run').innerHTML='Run again <span>↗</span>';}
}
for(const button of document.querySelectorAll('.stage'))button.addEventListener('click',()=>{
  if(busy)return;mode=button.dataset.mode;playing=false;run=null;runs=[];cycle=0;ms=0;
  for(const b of document.querySelectorAll('.stage'))b.classList.toggle('selected',b===button);
  $('run').innerHTML='Run experiment <span>↗</span>';$('message').textContent='';
  $('survivors').textContent='6/6';$('harm').textContent='0';$('feeding').textContent='100%';updatePanels();draw();
});
$('run').addEventListener('click',()=>start());
$('pause').addEventListener('click',()=>{if(run){playing=!playing;lastTime=0;$('pause').textContent=playing?'Pause':'Play';}});
$('next').addEventListener('click',()=>{if(run){moveScene(cycle<5?cycle+1:0);playing=!reduced;$('pause').textContent=playing?'Pause':'Play';}});
$('seek').addEventListener('input',()=>{if(run){playing=false;ms=Number($('seek').value);$('pause').textContent='Play';draw();}});
function fullscreen(){if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen?.();}
$('full').addEventListener('click',fullscreen);
$('inspect').addEventListener('click',()=>$('inspector').showModal());$('closeInspector').addEventListener('click',()=>$('inspector').close());
for(const [id,value] of [['muteRecall','no_replay'],['muteMotor','no_motor'],['restore','normal']])$(id).addEventListener('click',()=>{if(!run)return;$('inspector').close();start(value,cycle);});
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'||$('inspector').open)return;if(e.code==='Space'){e.preventDefault();$('pause').click();}if(e.key==='ArrowRight')$('next').click();if(e.key.toLowerCase()==='f')fullscreen();});
if(window.WORKSHOP_DATA){$('codeBadge').textContent='Offline replay';}
else fetch('/api/status').then(r=>r.json()).then(data=>$('codeBadge').textContent=data.code).catch(()=>$('codeBadge').textContent='Server unavailable');
requestAnimationFrame(tick);
