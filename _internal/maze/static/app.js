/* One verified event log drives the maze, retrieved images, and neural activity. */
const $ = id => document.getElementById(id);
const COLORS = {mint:'#8ce5c0',pink:'#ff527d',purple:'#b49aff',blue:'#83ccff',muted:'#b7b4ca',white:'#f5f2fa'};
const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
let seed=300, focusIndex=5;
let flyButtons=[];
let mode='none', bundle=null, world=null, busy=false, playing=false, elapsed=0, lastTime=0, speed=2;
let disconnected=false;
let positions=null, brainBackground=null, projectNeuron=null, lastEvidence='';
function playbackSource(){return window.WORKSHOP_DATA?'Recorded fallback':bundle?.failed?'Interrupted computation':bundle?.streaming?'Live computation':'Computed now';}

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
  const signature=`${bundle.hero.owner}:${mode}:${decision?.time}`;
  const count=mode==='shared'?bundle.initial_memories.length:currentMemories().length;
  $('memory-count').textContent=mode==='none'?'Off':mode==='personal'?`${bundle.hero.owner} · ${count} stored`:`A group · ${count} stored`;
  if(signature===lastEvidence)return;
  lastEvidence=signature;
  const matched=decision?.views.find(v=>v.applied), view=matched||decision?.views.find(v=>v.hits.length)||decision?.views[decision.choice];
  const hit=view?.selected||view?.hits?.[0];
  const record=hit&&currentMemories().find(o=>o.id===hit.id||o.payload.snapshot===hit.payload.snapshot);
  imageInto('current-view',view?.image_url,!!matched);imageInto('stored-view',record?.image_url,!!matched);
  const option=decision?.candidates?.indexOf(decision.views.indexOf(view));
  $('current-caption').textContent=view?`${mode==='none'?'View':'Query'}: ${option===0?'left':option===1?'right':'entrance'}`:'Current view';
  $('stored-caption').textContent=hit?`Returned: ${hit.payload.source_fly}`:'Returned memory';
  const searched=view?.search_ms!=null;
  $('returned-count').textContent=searched?String(view.hits.length):'—';
  $('cosine-score').textContent=hit?Number(hit.score).toFixed(3):'—';
  $('search-time').textContent=searched?`${view.search_ms<.01?'<0.01':view.search_ms.toFixed(2)}`:'—';
  $('memory-title').textContent=mode==='none'?'Retrieval is off.':!decision?'Search the visible entrance.':matched?'Memory changes the input.':hit?'A similar view returned.':searched?'No match ≥ 0.90.':'No usable view.';
  $('evidence-result').textContent=hit?(hit.payload.outcome==='returned'?'Returned to start.':hit.payload.outcome==='dead_end'?'Reached a dead end.':'Reached another opening.'):mode==='none'?'The brain explores.':!decision?'Waiting for a junction.':searched?'The brain explores.':'Not searched.';
  $('evidence-result').classList.toggle('hit',!!matched);
  $('provenance').textContent=hit?`${hit.payload.source_fly} observed it. ${matched?`${bundle.hero.owner} uses it.`:'Returned, not applied.'}`:'';
}
function selectFly(index){
  if(!bundle)return;
  focusIndex=Math.min(index,bundle.flies.length-1);
  bundle.hero=bundle.flies[focusIndex];bundle.ghost=bundle.comparisons[focusIndex]||null;
  $('hero-name').textContent=`Fly ${bundle.hero.owner||'A'}`;
  $('playback-source').textContent=playbackSource();
  $('ghost-key').hidden=!bundle.ghost;
  $('ghost-key').replaceChildren(Object.assign(document.createElement('i'),{className:'ghost-dot'}),document.createTextNode(disconnected?' Connected run':mode==='shared'?' Personal run':' No-memory run'));
  lastEvidence='';update();
}
function groupControls(){
  flyButtons=bundle.flies.map((run,index)=>{
    const button=document.createElement('button');button.textContent=run.owner||`A${index+1}`;
    button.setAttribute('aria-label',`Inspect fly ${button.textContent}`);
    button.addEventListener('click',()=>selectFly(index));return button;
  });
  $('fly-selector').replaceChildren(...flyButtons);
}
function playbackEnd(){return Math.max(...bundle.flies.map(r=>r.summary.time_ms),bundle.ghost?.summary.time_ms||0);}

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
  g.beginPath();g.roundRect(ex-36,ey-58,72,34,5);g.fill();g.stroke();label(g,'EXIT',ex,ey-35,18,COLORS.mint,'center');
  const [gx,gy]=point(world.exit[0]-20,world.exit[1]);g.strokeStyle=COLORS.mint;g.lineWidth=3;g.beginPath();g.moveTo(gx,gy-35*scale);g.lineTo(gx,gy+35*scale);g.stroke();
  const [sx,sy]=point(world.start[0],world.start_line?.[2]||world.start[1]);
  g.strokeStyle='#5b506d';g.lineWidth=3;g.beginPath();g.moveTo(sx-40*scale,sy);g.lineTo(sx+40*scale,sy);g.stroke();
  label(g,'START',sx,sy+26,14,'#43394f','center');
  const [lx,ly]=point(150,430);label(g,'LOOP',lx,ly,19,COLORS.muted,'center');
  function trail(run,color,ghost){
    if(!run)return;
    g.beginPath();let started=false;
    for(let i=0;i<run.frames.length;i+=5){const f=run.frames[i];if(f.ms>elapsed)break;const [x,y]=point(f.x,f.y);if(!started){g.moveTo(x,y);started=true;}else g.lineTo(x,y);}
    g.lineWidth=ghost?2:3;g.strokeStyle=color;g.globalAlpha=ghost?.35:.85;g.setLineDash(ghost?[4,6]:[]);g.stroke();g.setLineDash([]);g.globalAlpha=1;
  }
  trail(bundle?.ghost,'#7e7b94',true);
  for(const run of bundle?.flies||[])if(run!==bundle.hero)trail(run,heroColor,true);
  trail(bundle?.hero,heroColor,false);
  for(const [index,run] of (bundle?.flies||[]).entries()){
    if(run===bundle.hero)continue;const frame=frameAt(run,elapsed);if(!frame)continue;
    const [x,y]=point(frame.x,frame.y);g.fillStyle='#222439';g.strokeStyle=heroColor;g.lineWidth=1.5;
    g.beginPath();g.arc(x,y,10,0,Math.PI*2);g.fill();g.stroke();label(g,String(index+1),x,y+4,11,heroColor,'center');
  }
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
    const f=frameAt(bundle.hero,decision.capture_time??decision.time), [x,y]=point(f.x,f.y);
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
    const frames=bundle.hero.frames,fired=new Set();
    for(let i=Math.max(0,Math.floor(elapsed/20)-5);i<frames.length&&i<=Math.floor(elapsed/20);i++){
      const f=frames[i];if(f.ms>elapsed||f.ms<elapsed-100)continue;
      g.globalAlpha=Math.max(.1,1-(elapsed-f.ms)/120);g.fillStyle=COLORS.mint;
      for(const id of f.neural.ids){fired.add(id);const [x,y]=projectNeuron(id);g.fillRect(x-1,y-1,2,2);}
    }
    g.globalAlpha=1;
    for(const [side,color] of [['left',COLORS.purple],['right',COLORS.pink]]){
      g.strokeStyle=color;g.fillStyle=color;
      for(const id of bundle.brain.readout[side]){const [x,y]=projectNeuron(id),active=fired.has(id);g.beginPath();g.arc(x,y,active?3.5:2,0,Math.PI*2);if(active)g.fill();else g.stroke();}
    }
  }
  const neural=current?.neural;
  const calibration=bundle?.brain.calibration,scale=100/((calibration?.reference||250)*1.6);
  $('left-bar').style.width=`${Math.min(100,(neural?.rateL||0)*(calibration?.gainL||1)*scale)}%`;
  $('right-bar').style.width=`${Math.min(100,(neural?.rateR||0)*(calibration?.gainR||1)*scale)}%`;
  $('turn').textContent=disconnected?'Disconnected':current?.deliberating?((current.neural.steer||0)<0?'Chooses left':'Chooses right'):(current?.applied_yaw||0)<-.08?'Left':(current?.applied_yaw||0)>.08?'Right':'Straight';
  $('input').classList.toggle('choosing',!!current?.deliberating);
  $('input').textContent=`${current?.deliberating?'Choice input':'Steering input'}: ${Math.round(current?.left_input||0)} / ${Math.round(current?.right_input||0)} Hz`;
}
function update(){
  drawWorld();drawBrain();evidence();
  $('timer').replaceChildren(document.createTextNode((Math.min(elapsed,bundle?.hero.summary.time_ms??elapsed)/1000).toFixed(1)),Object.assign(document.createElement('span'),{textContent:'s'}));
  if(!bundle)return;
  const done=bundle.hero.complete!==false&&elapsed>=bundle.hero.summary.time_ms;
  const exited=bundle.flies.filter(r=>r.summary.exit&&elapsed>=r.summary.time_ms).length;
  $('group-result').textContent=`${exited}/${bundle.flies.length}`;
  flyButtons.forEach((button,index)=>{
    const run=bundle.flies[index],finished=run.complete!==false&&elapsed>=run.summary.time_ms;
    button.setAttribute('aria-pressed',String(index===focusIndex));
    button.classList.toggle('finished',finished&&run.summary.exit);
    button.classList.toggle('timeout',finished&&!run.summary.exit);
    button.setAttribute('aria-label',`Inspect ${run.owner}. ${finished?(run.summary.exit?'Reached exit':'Time expired'):'Exploring'}.`);
  });
  $('replay-memory').hidden=!bundle.hero.decisions.some(d=>d.time<=elapsed&&d.views.some(v=>v.applied));
  $('result').textContent=done?(bundle.hero.summary.exit?`Exit found in ${(bundle.hero.summary.time_ms/1000).toFixed(1)} s`:(bundle.hero.summary.no_decision?'No neural decision.':`No exit within 65 s.`)):'';
  const d=latestDecision(),terminal=bundle.hero.events.findLast(e=>e.kind==='observed'&&['returned','dead_end'].includes(e.outcome)&&e.time<=elapsed);
  $('scene-caption').textContent=terminal&&elapsed-terminal.time<1800?mode==='none'?'An observed outcome. Memory is off.':mode==='shared'?'An outcome is recorded. The A-group memory stays fixed.':`An observed outcome becomes ${bundle.hero.owner}’s memory.`:d&&elapsed-d.time<2300?(d.views.some(v=>v.selected)?mode==='shared'?'Another fly’s observation changes this input.':'Its own observation changes this input.':mode==='none'?'Balanced input. The neural readout chooses.':'No matching memory. The brain explores.') :'';
  if(done&&bundle.ghost&&elapsed<bundle.ghost.summary.time_ms)$('scene-caption').textContent='Exit reached. The comparison is still exploring.';
  $('pause').textContent=playing?'Pause':'Resume';
  $('playback-source').textContent=playbackSource();
}
function tick(time){
  if(playing&&bundle){
    const delta=lastTime?Math.min(80,time-lastTime):0;lastTime=time;
    const end=playbackEnd(),available=bundle.streaming||bundle.failed?Math.min(end,bundle.buffer_ms):end;
    elapsed=Math.min(available,elapsed+delta*speed);
    if(elapsed>=end&&!bundle.streaming){playing=false;$('pause').disabled=true;$('message').textContent=mode==='none'?'Build personal memory in memory.py.':mode==='personal'?'Share the observed experience in pipeline.py.':'The new group used completed A-group experience.';}
    update();
  }
  requestAnimationFrame(tick);
}
function begin(data,streaming=false){
  bundle={...data,flies:data.flies||[data.hero],comparisons:data.comparisons||(data.ghost?[data.ghost]:[]),streaming,buffer_ms:0};
  if(streaming)for(const fly of bundle.flies)fly.complete=false;
  world=data.world;elapsed=0;lastEvidence='';lastTime=0;playing=true;
  groupControls();selectFly(focusIndex);
  document.body.dataset.mode=mode;
  $('chapter').textContent=mode==='none'?'EIGHT INDEPENDENT BRAINS':mode==='personal'?'EMPTY MEMORY AT THE START':'NEW FLIES, COMPLETED GROUP EXPERIENCE';
  $('headline').textContent=mode==='none'?'How many find the exit?':mode==='personal'?'Each fly learns for itself.':'New flies share experience.';
  $('message').textContent=`${data.code||'Completed code'}. ${playbackSource()}.`;
  $('run').textContent=mode==='none'&&!window.WORKSHOP_DATA?'New group':'Run again';$('pause').disabled=false;update();
}
function receive(message){
  if(message.type==='error')throw Error(message.detail);
  if(message.type==='begin'){begin(message.data,true);return;}
  if(!bundle?.streaming)throw Error('The live run sent data before its starting state.');
  if(message.type==='batch'){
    for(const item of message.flies){
      const fly=bundle.flies[item.index];
      for(const key of ['frames','decisions','events','observations'])fly[key].push(...item[key]);
      if(item.summary){fly.summary=item.summary;fly.complete=true;}
    }
    bundle.buffer_ms=message.ms;
    $('computing').hidden=true;
    if(!playing)update();
  }else if(message.type==='complete'){
    bundle.streaming=false;bundle.cohort.summary=message.summary;
    if(!disconnected)(bundle.cohort.stages??={})[mode]=message.summary;
    $('message').textContent=`${bundle.code}. Computed now. All eight runs are available.`;
    update();
  }else throw Error('The live run sent an unknown event.');
}
async function readLive(response){
  if(!response.body?.getReader)throw Error('The browser cannot read the live run.');
  const reader=response.body.getReader(),decoder=new TextDecoder();
  let pending='',complete=false;
  try{
    while(true){
      const {value,done}=await reader.read();
      pending+=decoder.decode(value,{stream:!done});
      let newline;
      while((newline=pending.indexOf('\n'))!==-1){
        const line=pending.slice(0,newline).trimEnd();pending=pending.slice(newline+1);
        if(line.startsWith('data: ')){const message=JSON.parse(line.slice(6));receive(message);complete=message.type==='complete';}
      }
      if(done)break;
    }
    if(pending.trim()||!complete)throw Error('The live connection ended before the group finished. Run again to retry.');
  }finally{await reader.cancel();reader.releaseLock();}
}
function selectStage(next){
  if(busy)return;
  mode=next;for(const button of document.querySelectorAll('.stage')){const selected=button.dataset.mode===mode;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));}
  start();
}
async function start(){
  if(busy)return;
  busy=true;playing=false;$('run').disabled=true;$('pause').disabled=true;$('computing').hidden=false;
  for(const button of document.querySelectorAll('.stage'))button.disabled=true;
  $('message').textContent=window.WORKSHOP_DATA?'Loading the recorded run.':'Starting eight independent brains…';
  try{
    await ready;
    if(mode==='none'&&bundle&&!disconnected&&!window.WORKSHOP_DATA){seed=Math.floor(Math.random()*1000000);}
    if(window.WORKSHOP_DATA){
      const data=window.WORKSHOP_DATA.runs[`${mode}:${disconnected?'mute':'normal'}`];
      if(!data)throw Error('This control is available in the live workshop.');
      begin(structuredClone(data));
    }else{
      $('computing-label').textContent='Starting eight independent brains…';
      const response=await fetch('/api/live',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode,seed,count:8,disconnect:disconnected})});
      if(!response.ok){const error=await response.json();throw Error(typeof error.detail==='string'?error.detail:'The run request failed.');}
      await readLive(response);
    }
  }catch(error){
    playing=false;if(bundle){bundle.failed=true;bundle.streaming=false;}
    $('pause').disabled=true;update();$('message').textContent=error.message;
  }finally{
    busy=false;$('run').disabled=false;$('computing').hidden=true;
    for(const button of document.querySelectorAll('.stage'))button.disabled=false;
  }
}
const ready=(async()=>{
  if(window.WORKSHOP_DATA){const bytes=Uint8Array.from(atob(window.WORKSHOP_DATA.positions_b64),c=>c.charCodeAt(0));positions=new Float32Array(bytes.buffer);world=window.WORKSHOP_DATA.world;}
  else {const responses=await Promise.all([fetch('/assets/brain-positions.bin'),fetch('/api/status')]);if(responses.some(r=>!r.ok))throw Error('The display could not load. Restart the workshop.');positions=new Float32Array(await responses[0].arrayBuffer());const status=await responses[1].json();world=status.world;seed=status.default_seed??300;$('message').textContent=`${status.code}. Start with No memory.`;}
  prepareBrain();update();
})();
ready.catch(error=>$('message').textContent=error.message);
$('run').addEventListener('click',start);
for(const button of document.querySelectorAll('.stage'))button.addEventListener('click',()=>selectStage(button.dataset.mode));
$('pause').addEventListener('click',()=>{if(!bundle)return;playing=!playing;lastTime=0;update();});
$('speed').addEventListener('click',()=>{speed=speed===2?1:speed===1?4:2;$('speed').textContent=`${speed}× speed`;$('speed').setAttribute('aria-label',`Simulation display speed ${speed} times. Change speed.`);});
$('disconnect').addEventListener('click',()=>{if(busy)return;disconnected=!disconnected;$('disconnect').setAttribute('aria-pressed',String(disconnected));if(bundle)start();});
$('fullscreen').addEventListener('click',()=>{const request=document.documentElement.requestFullscreen?.();request?.catch?.(()=>$('message').textContent='Use the browser’s full-screen control.');});
$('inspect').addEventListener('click',()=>{const decision=latestDecision();
  const rows=(decision?.views||[]).flatMap((view,option)=>(view.hits||[]).map((hit,rank)=>`<tr><td>${option+1}</td><td>${rank+1}</td><td>${String(hit.payload.source_fly).replace(/[^A-Za-z0-9]/g,'')}</td><td>${hit.payload.outcome}</td><td>${Number(hit.score).toFixed(4)}</td><td>${view.search_ms?.toFixed(3)} ms</td><td>${view.applied&&view.selected?.id===hit.id?'Used':'Returned'}</td></tr>`));
  $('retrieval-table').innerHTML=rows.length?`<table><thead><tr><th>View</th><th>Rank</th><th>Source</th><th>Outcome</th><th>Cosine</th><th>Search</th><th>Policy</th></tr></thead><tbody>${rows.join('')}</tbody></table>`:'No records returned at this decision.';
  $('details').textContent=JSON.stringify(bundle?{source:playbackSource(),mode,seed:bundle.hero.seed,summary:bundle.hero.summary,group:bundle.cohort,comparison:bundle.ghost?.summary,current_decision:latestDecision(),neural_frame:frameAt(bundle.hero,elapsed),memory_protocol:bundle.initial_memories[0]?.payload.protocol} :{status:'Run the demo to inspect its evidence.'},null,2);$('inspector').showModal();});
$('replay-memory').addEventListener('click',()=>{const decision=bundle?.hero.decisions.find(d=>d.views.some(v=>v.applied));if(!decision)return;elapsed=decision.time;playing=false;lastTime=0;$('pause').disabled=false;update();$('message').textContent='Paused at the first use of retrieved experience.';});
$('close-inspector').addEventListener('click',()=>$('inspector').close());
window.addEventListener('resize',()=>{prepareBrain();update();});
document.addEventListener('keydown',event=>{if(['INPUT','TEXTAREA'].includes(event.target.tagName)||$('inspector').open)return;if(event.code==='Space'){event.preventDefault();$('pause').click();}else if(event.key==='r')start();else if(['1','2','3'].includes(event.key))selectStage(['none','personal','shared'][Number(event.key)-1]);});
requestAnimationFrame(tick);
