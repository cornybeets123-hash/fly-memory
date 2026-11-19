/* Webinar controls use the same recorded frames and evidence as the workshop inspector. */
let population='live', hiveStatus={ready:[],state:'missing'}, selectionRequest=0;
let presentationView=window.WEBINAR_PRESENTATION?'race':'explain',raceLoading=false;
const liveStart=start, liveSelectFly=selectFly;
const measured={live:{},hive:{}};
const flyCount=()=>hiveStatus.count||200;
function applyFlyCount(){for(const el of document.querySelectorAll('[data-count]'))el.textContent=flyCount().toLocaleString();}
const populationRuns=new Map();
window.webinarOnBegin=data=>{if(!data.population){measured.live={...(data.cohort?.stages||{})};comparisonTable();}};
function drawPopulationGrid(){
  if(window.WEBINAR_PRESENTATION)return;
  $('population-ledger').hidden=!bundle?.population;
  if(!bundle?.population)return;
  const {g,w,h}=canvas('population-grid'),columns=50,rows=Math.ceil(bundle.flies.length/columns),cw=w/columns,ch=h/rows;
  for(const [i,run] of bundle.flies.entries()){
    const done=elapsed>=run.summary.time_ms,exited=done&&run.summary.exit,x=(i%columns)*cw,y=Math.floor(i/columns)*ch;
    g.fillStyle=exited?COLORS.mint:done?COLORS.pink:'#48465e';g.fillRect(x+1,y+1,Math.max(1,cw-2),Math.max(1,ch-2));
    if(done&&!exited){g.strokeStyle='#171525';g.lineWidth=1;g.beginPath();g.moveTo(x+2,y+2);g.lineTo(x+cw-2,y+ch-2);g.moveTo(x+cw-2,y+2);g.lineTo(x+2,y+ch-2);g.stroke();}
    if(i===focusIndex){g.strokeStyle=COLORS.white;g.lineWidth=2;g.strokeRect(x,y,cw,ch);}
  }
}

function metric(value,digits=0){return Number.isFinite(value)?value.toLocaleString(undefined,{maximumFractionDigits:digits}):'Unmeasured';}
function comparisonTable(){
  const rows=measured[population];
  const labels={none:'No memory',personal:'Personal',shared:'Shared'};
  const cells=Object.entries(rows).map(([key,s])=>`<tr><th scope="row">${labels[key]}</th><td>${s.exited}/${s.count}</td><td>${metric(s.mean_time_ms/1000,1)} s</td><td>${metric(s.mean_path)}</td><td>${metric(s.returns)}</td><td>${metric(s.dead_ends)}</td><td>${metric(s.collisions)}</td><td>${metric(s.false_exclusions)}</td></tr>`);
  $('behavior-table').innerHTML=cells.length?`<table><thead><tr><th>Condition</th><th>Exits</th><th>Mean time</th><th>Mean path (units)</th><th>START returns</th><th>Dead ends</th><th>Collisions</th><th>False exclusions</th></tr></thead><tbody>${cells.join('')}</tbody></table>`:'Run the conditions to compare behavior.';
  const failures=population==='hive'?Object.entries(hiveStatus.behavior_failures||{}).flatMap(([condition,attempts])=>attempts.map(f=>`${labels[condition]}: ${f.fly} (seed ${f.seed}) stopped ${f.reason==='ambiguous_options'?'at an ambiguous fork':'after a zero neural readout'}.`)):[];
  $('behavior-failures').textContent=failures.length?`${failures.join(' ')} All stopped attempts remain in the results.`:'';
}
window.webinarAfterUpdate=()=>{
  drawPopulationGrid();
  if(!bundle)return;
  if(bundle.turn_replay&&!playing&&elapsed>=bundle.turn_replay.end_ms){cancelTurnReplay();$('pause').disabled=false;$('message').textContent='Paused after the recorded turn. Inspect the observation or continue the run.';}
  $('search-time-label').textContent=bundle.population?'Recorded search · ms':'Search · ms';
  const deadline=bundle.cohort?.deadline_ms??180000;
  $('seek').disabled=false;$('seek').max=String(bundle.streaming?bundle.buffer_ms:deadline);$('seek').value=String(elapsed);
  $('seek-time').textContent=`${(elapsed/1000).toFixed(1)} / ${deadline/1000} s`;
  $('brain-time').textContent=`Fly time · ${((frameAt(bundle.hero,elapsed)?.ms||0)/1000).toFixed(1)} s`;
  const hit=junctionEvidence(shownDecision()).hit;
  const outcome=hit?.payload.outcome==='returned'?'returned to START':hit?.payload.outcome.replace('_',' ');
  $('visible-provenance').textContent=hit?`${hit.payload.source_fly} observed “${outcome}”. ${bundle.hero.owner} ${junctionEvidence(shownDecision()).applied?'uses that evidence.':'keeps both options.'}`:mode==='shared'?`All ${bundle.flies.length} flies start with one empty memory. Each completed observation is written at once, and every fly reads it.`:mode==='personal'?'Each fly can retrieve only its own completed observations.':'Each fly explores without external memory.';
  if(!bundle.streaming&&bundle.cohort?.summary){
    const summary=bundle.cohort.summary;
    if(measured[population][mode]!==summary){measured[population][mode]=summary;comparisonTable();if(summary.audit_errors?.length)$('message').textContent='Evidence audit failed. Inspect the raw results before presenting this run.';}
  }
};
$('seek').addEventListener('input',()=>{if(!bundle)return;elapsed=Number($('seek').value);bundle.presentation_end_ms=bundle.cohort?.deadline_ms??180000;playing=false;lastTime=0;$('pause').disabled=false;lastEvidence='';update();});

async function overview(condition){
  if(!populationRuns.has(condition)){
    const response=await fetch(`/api/hive/${condition}`);
    if(!response.ok){const error=await response.json();throw Error(error.detail||'The population is not ready.');}
    populationRuns.set(condition,await response.json());
  }
  return populationRuns.get(condition);
}
window.loadPopulationFly=async index=>{
  cancelTurnReplay();
  const requested=++selectionRequest,current=bundle;
  const previousPlaying=playing;playing=false;
  $('message').textContent=`Loading the recorded evidence for ${current.flies[index].owner}…`;
  try{
    const response=await fetch(`/api/hive/${mode}/fly/${index}`);
    if(!response.ok)throw Error('The recorded evidence could not load. Select the fly again to retry.');
    const detail=await response.json();
    if(requested!==selectionRequest||current!==bundle)return;
    bundle.flies[index]={...detail.run,detailLoaded:true};bundle.initial_memories=detail.initial_memories;
    playing=previousPlaying;lastTime=0;liveSelectFly(index);
    $('message').textContent=detail.behavior_failure?`${detail.run.owner} stopped at ${(detail.run.summary.time_ms/1000).toFixed(1)} s. This unsuccessful attempt remains in the comparison.`:'Recorded population. Every marker follows its own computed neural run.';
  }catch(error){if(requested===selectionRequest)$('message').textContent=error.message;}
};
selectFly=function(index){
  if(bundle?.population&&!(index===focusIndex&&bundle.flies[index]?.detailLoaded)){window.loadPopulationFly(index);return;}
  liveSelectFly(index);
};
async function startPopulation(options={}){
  cancelTurnReplay();
  if(population==='live'){await liveStart(options);return;}
  if(busy)return;
  busy=true;playing=false;$('run').disabled=true;$('computing').hidden=false;
  $('computing-label').textContent='Loading actual recorded trajectories…';
  for(const button of document.querySelectorAll('.stage'))button.disabled=true;
  const previous=bundle,selectedMode=mode;
  try{
    await ready;
    const data=await overview(selectedMode),comparison=selectedMode!=='none'?await overview('none'):null;
    if((data.evidence_errors??data.audit_errors).length)throw Error('This condition failed its evidence audit. Inspect the preparation log.');
    const response=await fetch(`/api/hive/${selectedMode}/fly/${focusIndex}`);
    if(!response.ok)throw Error('The selected fly’s evidence could not load.');
    const detail=await response.json();
    const flies=data.flies.map(r=>({...r,decisions:[],events:[],observations:[],detailLoaded:false}));
    flies[focusIndex]={...detail.run,detailLoaded:true};
    disconnected=false;
    begin({mode:selectedMode,flies,comparisons:comparison?.flies||[],population:true,
      presentation_end_ms:selectedMode==='shared'?60000:180000,
      initial_memories:detail.initial_memories,memory_count:hiveStatus.memory_count,memory_times:data.memory_times,
      comparison_mode:'none',world,brain:data.brain,code:'Recorded population',
      cohort:{seeds:flies.map(r=>r.seed),deadline_ms:180000,summary:data.summary}});
    $('disconnect').hidden=true;$('run').textContent=`Replay ${flyCount()} flies`;$('message').textContent='Recorded population. Each fly follows its own computed run.';
  }catch(error){
    bundle=previous;if(previous)mode=previous.mode;
    for(const button of document.querySelectorAll('.stage')){button.classList.toggle('selected',button.dataset.mode===mode);button.setAttribute('aria-pressed',String(button.dataset.mode===mode));}
    $('message').textContent=error.message;
  }finally{busy=false;$('run').disabled=false;$('computing').hidden=true;for(const button of document.querySelectorAll('.stage'))button.disabled=false;}
}
start=async function(options={}){if(window.WEBINAR_PRESENTATION&&presentationView==='race')return startRace();return startPopulation(options);};
function choosePopulation(next){
  if(busy)return;
  population=next;playing=false;bundle=null;elapsed=0;mode='none';selectionRequest++;
  $('live-population').setAttribute('aria-pressed',String(next==='live'));
  $('hive-population').setAttribute('aria-pressed',String(next==='hive'));
  for(const button of document.querySelectorAll('.stage')){button.classList.toggle('selected',button.dataset.mode==='none');button.setAttribute('aria-pressed',String(button.dataset.mode==='none'));}
  $('disconnect').hidden=next==='hive';$('run').textContent=next==='hive'?`Play ${flyCount()} flies`:'Run eight flies';
  $('group-result').textContent=next==='hive'?`0/${flyCount()}`:'0/8';$('fly-selector').replaceChildren();
  $('pause').disabled=true;$('seek').disabled=true;
  $('message').textContent=next==='hive'?'The population uses recorded, independently computed neural runs.':'Start No memory, then Personal memory, then Shared memory.';
  comparisonTable();lastEvidence='';update();
  $('population-ledger').hidden=next!=='hive';
  document.body.dataset.population=next;
}
$('population-grid').addEventListener('click',event=>{if(!bundle?.population)return;const box=$('population-grid').getBoundingClientRect(),columns=50,rows=Math.ceil(bundle.flies.length/columns),index=Math.floor((event.clientY-box.top)/box.height*rows)*columns+Math.floor((event.clientX-box.left)/box.width*columns);if(index>=0&&index<bundle.flies.length){$('population-fly').value=String(index);selectFly(index);}});
$('live-population').addEventListener('click',()=>{choosePopulation('live');if(window.WEBINAR_PRESENTATION)setPresentationView('explain');});
$('hive-population').addEventListener('click',()=>choosePopulation('hive'));
async function refreshHive(){
  try{
    const response=await fetch('/api/hive/status');if(!response.ok)throw Error('Population status is unavailable.');
    hiveStatus=await response.json();applyFlyCount();
    const state=hiveStatus.state;
    $('hive-status').textContent=state==='ready'||state==='ready_with_failures'?`${flyCount().toLocaleString()} flies measured in all three conditions. Stopped attempts remain included.`:state==='missing'?'Prepare the population before the webinar.':state==='computing'||state==='starting'?`${hiveStatus.done.toLocaleString()} / ${hiveStatus.total.toLocaleString()} trials computed · ${hiveStatus.mode||'starting'}`:state==='stale'?'Population source changed. Archive earlier artifacts and prepare again.':state==='audit_failed'?'Population evidence audit failed. Read compute.log.':`Population ${state}${hiveStatus.detail?`: ${hiveStatus.detail}`:''}.`;
    $('prepare-hive').hidden=state==='ready'||state==='ready_with_failures';$('prepare-hive').disabled=['computing','starting','stale','audit_failed'].includes(state);
    $('cancel-hive').hidden=!['computing','starting'].includes(state);
    $('hive-population').disabled=!hiveStatus.ready.includes('none');
    measured.hive=hiveStatus.summary||{};if(population==='hive')comparisonTable();
  }catch(error){$('hive-status').textContent=error.message;}
}
$('prepare-hive').addEventListener('click',async()=>{try{const response=await fetch('/api/hive/prepare',{method:'POST'});if(!response.ok){const error=await response.json();throw Error(error.detail);}await refreshHive();}catch(error){$('hive-status').textContent=error.message;}});
$('cancel-hive').addEventListener('click',async()=>{try{const response=await fetch('/api/hive/cancel',{method:'POST'});if(!response.ok)throw Error('Preparation could not stop.');await refreshHive();}catch(error){$('hive-status').textContent=error.message;}});
window.webinarReady=ready.then(async()=>{
  if(window.WEBINAR_PRESENTATION){
    await refreshHive();
    choosePopulation(hiveStatus.ready.includes('shared')?'hive':'live');
    setPresentationView('race');
    $('replay-memory').textContent='Replay this turn';
  }else{choosePopulation('live');refreshHive();}
  setInterval(refreshHive,5000);
});
window.webinarReady.catch(error=>$('message').textContent=error.message);

window.webinarPlaybackEnd=data=>data?.population?(data.turn_replay?.end_ms??data.presentation_end_ms??Math.max(...data.flies.map(r=>r.summary.time_ms))):undefined;
window.webinarHeadline=condition=>({none:'Explore without memory.',personal:'Use your own experience.',shared:'Build one memory together.'}[condition]);

const raceBackgrounds=new Map();
function raceMaze(id,runs,time,color){
  const {g,w,h,dpr}=canvas(id);if(!world||w<2||h<2)return;
  const [x0,y0,x1,y1]=world.bounds,pad=12,scale=Math.min((w-pad*2)/(x1-x0),(h-pad*2)/(y1-y0));
  const ox=(w-(x1-x0)*scale)/2-x0*scale,oy=(h-(y1-y0)*scale)/2-y0*scale;
  const key=`${w}:${h}:${dpr}:${world.bounds.join(',')}`;
  let background=raceBackgrounds.get(key);
  if(!background){
    background=document.createElement('canvas');background.width=Math.round(w*dpr);background.height=Math.round(h*dpr);
    const bg=background.getContext('2d');bg.scale(dpr,dpr);bg.save();bg.translate(ox,oy);bg.scale(scale,scale);
    bg.fillStyle='#ddd9c5';bg.beginPath();for(const [a,b,c,d] of world.rectangles)bg.rect(a,c,b-a,d-c);bg.fill();
    bg.strokeStyle='#848da0';bg.lineWidth=1.5/scale;bg.beginPath();for(const [a,b,c,d] of world.walls){bg.moveTo(a,b);bg.lineTo(c,d);}bg.stroke();
    for(const [x,y,rgb,radius] of world.landmarks){bg.fillStyle=`rgb(${rgb.join(',')})`;bg.beginPath();bg.arc(x,y,radius,0,Math.PI*2);bg.fill();}
    bg.restore();const ex=ox+world.exit[0]*scale,ey=oy+world.exit[1]*scale;
    label(bg,'EXIT',ex,Math.max(16,ey-15),12,COLORS.mint,'center');
    const startY=world.start_line?.[2]??world.start[1];
    label(bg,'START',ox+(world.start[0]-65)*scale,oy+startY*scale+4,11,COLORS.muted,'right');
    raceBackgrounds.set(key,background);if(raceBackgrounds.size>6)raceBackgrounds.delete(raceBackgrounds.keys().next().value);
  }
  g.drawImage(background,0,0,w,h);
  drawCrowdSamples(id.replace('-world','-samples'),runs,time,color,background,{scale,ox,oy,dpr});
  drawCrowd(g,runs,time,(x,y)=>[ox+x*scale,oy+y*scale],color,h);
  const tracked=movementFrameAt(runs[focusIndex],time);
  if(tracked){
    g.save();g.translate(ox+tracked.x*scale,oy+tracked.y*scale);g.strokeStyle=color;g.lineWidth=1.5;g.beginPath();g.arc(0,0,12,0,Math.PI*2);g.stroke();
    if(typeof drawSpecimen==='function')drawSpecimen(g,8,tracked.heading,reducedMotion?0:time*.009,color);
    g.restore();
  }
}
// Every sprite uses its recorded position. Nearby flies overlap; badges count
// those overlaps instead of moving agents to decorative display positions.
const crowdSprites=new Map();
// Eight distinct trials spread across the whole population.
const sampleIndices=n=>Array.from({length:Math.min(8,n)},(_,i)=>Math.floor((i+.5)*n/Math.min(8,n)));
function drawCrowdSamples(id,runs,time,color,background,{scale,ox,oy,dpr}){
  const {g,w,h}=canvas(id),columns=4,cw=w/columns,ch=(h-17)/2;
  label(g,'Eight magnified flies',0,11,10,COLORS.muted);
  const picks=sampleIndices(runs.length);
  for(let i=0;i<8;i++){
    const run=runs[picks[i]],frame=run&&movementFrameAt(run,time);
    const x=i%columns*cw,y=17+Math.floor(i/columns)*ch,viewHeight=ch-12;
    g.fillStyle='#0d1020';g.fillRect(x,y,cw-4,viewHeight);
    if(frame){
      // Crop the same recorded world around each fly. The main map keeps its
      // absolute position; each inset follows one named, distinct trial.
      const px=ox+frame.x*scale,py=oy+frame.y*scale,zoom=1.5;
      g.drawImage(background,(px-(cw-4)/zoom/2)*dpr,(py-viewHeight/zoom/2)*dpr,(cw-4)/zoom*dpr,viewHeight/zoom*dpr,x,y,cw-4,viewHeight);
      const angle=((Math.round(frame.heading*12/Math.PI)%24)+24)%24;
      g.drawImage(crowdSprite(color,angle),x+(cw-4)/2-22,y+viewHeight/2-22,44,44);
      label(g,run.owner||`${id.includes('shared')?'H':'A'}${picks[i]+1}`,x+(cw-4)/2,y+ch-3,9,color,'center');
    }
    g.strokeStyle='#515b7766';g.lineWidth=1;g.strokeRect(x+.5,y+.5,cw-5,viewHeight-1);
  }
}
function crowdSprite(color,angle){
  const key=`${color}:${angle}`;if(crowdSprites.has(key))return crowdSprites.get(key);
  const sprite=document.createElement('canvas');sprite.width=36;sprite.height=36;
  const g=sprite.getContext('2d');g.translate(18,18);
  drawSpecimen(g,9,angle*Math.PI/12,0,color);
  crowdSprites.set(key,sprite);return sprite;
}
function drawCrowd(g,runs,time,point,color,height=Infinity){
  const clusters=[];
  for(const run of runs){
    const frame=movementFrameAt(run,time);if(!frame)continue;
    const [x,y]=point(frame.x,frame.y),angle=((Math.round(frame.heading*12/Math.PI)%24)+24)%24;
    g.drawImage(crowdSprite(color,angle),x-12,y-12,24,24);
    let cluster=clusters.find(c=>Math.hypot(x-c.x/c.count,y-c.y/c.count)<24);
    if(!cluster){cluster={x:0,y:0,count:0};clusters.push(cluster);}
    cluster.x+=x;cluster.y+=y;cluster.count++;
  }
  const badges=[];
  for(const cluster of clusters){
    if(cluster.count<5)continue;
    const x=cluster.x/cluster.count,y=cluster.y/cluster.count,text=String(cluster.count),width=12+text.length*7;
    let top=Math.min(height-20,y+13);
    while(badges.some(b=>Math.abs(x-b.x)<(width+b.width)/2+3&&Math.abs(top-b.top)<20))top-=20;
    badges.push({x,top,width});
    g.fillStyle='#0d1020ed';g.strokeStyle=color;g.lineWidth=1;
    g.beginPath();g.moveTo(x,top);g.lineTo(x,y+7);g.stroke();
    g.beginPath();g.roundRect(x-width/2,top,width,18,5);g.fill();g.stroke();
    label(g,text,x,top+13,11,color,'center');
  }
}
function raceLedger(id,runs,time,color){
  const {g,w,h}=canvas(id),total=Math.max(runs.length,flyCount());
  const columns=Math.max(1,Math.min(total,Math.round(Math.sqrt(total*w/Math.max(1,h))))),rows=Math.ceil(total/columns),cw=w/columns,ch=h/rows;
  for(let i=0;i<total;i++){
    const run=runs[i],done=!!run&&time>=run.summary.time_ms,exited=done&&run.summary.exit;
    const x=i%columns*cw,y=Math.floor(i/columns)*ch;
    g.fillStyle=exited?COLORS.mint:done?COLORS.pink:color;g.globalAlpha=done?1:.25;
    // One small fly per trial: two wings and a body, rather than a block.
    const cx=x+cw/2,cy=y+ch/2;
    g.beginPath();g.ellipse(cx-cw*.15,cy-ch*.12,cw*.19,ch*.25,-.5,0,Math.PI*2);g.ellipse(cx+cw*.15,cy-ch*.12,cw*.19,ch*.25,.5,0,Math.PI*2);g.fill();
    g.fillRect(cx-cw*.055,cy-ch*.28,Math.max(1,cw*.11),Math.max(1,ch*.62));
    if(done&&!exited){g.globalAlpha=1;g.strokeStyle='#141827';g.lineWidth=1;g.beginPath();g.moveTo(x+2,y+2);g.lineTo(x+cw-2,y+ch-2);g.moveTo(x+cw-2,y+2);g.lineTo(x+2,y+ch-2);g.stroke();}
  }
  g.globalAlpha=1;
}
window.webinarUpdateRace=()=>{
  if(!window.WEBINAR_PRESENTATION||presentationView!=='race')return false;
  const paired=bundle?.population&&bundle.mode==='shared',baseline=paired?bundle.comparisons:[],shared=paired?bundle.flies:[];
  raceMaze('race-none-world',baseline,elapsed,COLORS.blue);raceMaze('race-shared-world',shared,elapsed,COLORS.mint);
  raceLedger('race-none-grid',baseline,elapsed,COLORS.blue);raceLedger('race-shared-grid',shared,elapsed,COLORS.mint);
  const exits=runs=>runs.filter(run=>run.summary.exit&&elapsed>=run.summary.time_ms).length;
  const noMemory=exits(baseline),withMemory=exits(shared);
  $('race-none-count').textContent=noMemory.toLocaleString();$('race-shared-count').textContent=withMemory.toLocaleString();
  $('race-clock').textContent=(elapsed/1000).toFixed(1);
  $('race-source').textContent=`Recorded comparison · ${speed}× playback · 60-second checkpoint`;
  $('pause').textContent=playing?'Pause':'Resume';
  $('run').textContent=paired?'Replay comparison':'Play comparison';
  $('explain-turn').disabled=busy||raceLoading||!hiveStatus.ready.includes('shared');
  if(paired&&!playing&&elapsed>=60000)$('message').textContent=`At 60 simulation seconds: ${withMemory.toLocaleString()} exits with shared memory; ${noMemory.toLocaleString()} without memory.`;
  return true;
};
function setPresentationView(next){
  cancelTurnReplay();
  selectionRequest++;
  presentationView=next;document.body.dataset.view=next;
  $('race-stage').hidden=next!=='race';$('explanation-stage').hidden=next!=='explain';
  $('view-race').setAttribute('aria-pressed',String(next==='race'));
  $('view-explain').setAttribute('aria-pressed',String(next==='explain'));
  $('race-setup').textContent=next==='race'?'Shared flies start with one empty memory and fill it together. Both crowds use the same seeds.':'Inspect a newcomer’s captured view, source observation, sensory input, and actual neural choice.';
  $('run').textContent=next==='race'?'Play comparison':population==='hive'?`Replay ${flyCount()} flies`:'Run eight flies';
  if(next==='race'&&!(bundle?.population&&bundle.mode==='shared')){bundle=null;elapsed=0;playing=false;}
  if(next==='race'&&bundle)bundle.presentation_end_ms=60000;
  if(next==='race')$('message').textContent='Recorded comparison. Play both crowds to the 60-second checkpoint.';
  prepareBrain();update();requestAnimationFrame(()=>{prepareBrain();update();});
}
async function startRace(){
  await window.webinarReady;
  if(busy||raceLoading)return;
  if(!hiveStatus.ready.includes('shared')){$('message').textContent='Prepare the recorded population in Demo controls before playing the comparison.';return;}
  raceLoading=true;
  $('race-loading').hidden=false;$('message').textContent='Loading the matched recorded populations…';
  try{
    population='hive';mode='shared';
    document.body.dataset.population='hive';$('hive-population').setAttribute('aria-pressed','true');$('live-population').setAttribute('aria-pressed','false');
    await startPopulation();
    if(bundle?.population&&bundle.mode==='shared'){$('message').textContent='Recorded comparison. Watch both crowds on the same simulation clock.';$('pause').disabled=false;}
  }finally{raceLoading=false;$('race-loading').hidden=true;update();}
}
async function showExplanation(){
  if(busy||raceLoading)return;
  if(!(bundle?.population&&bundle.mode==='shared')){await startRace();if(!(bundle?.population&&bundle.mode==='shared'))return;}
  const decision=bundle.hero.decisions.find(d=>junctionEvidence(d).applied);
  elapsed=decision?.time??0;playing=false;lastTime=0;lastEvidence='';
  bundle.presentation_end_ms=bundle.cohort?.deadline_ms??180000;
  setPresentationView('explain');$('pause').disabled=false;
  $('message').textContent='Paused at an actual use of another fly’s completed observation.';
}
$('view-race').addEventListener('click',()=>{if(!busy&&!raceLoading){playing=false;elapsed=Math.min(elapsed,60000);setPresentationView('race');}});
$('view-explain').addEventListener('click',()=>{if(population==='live'&&presentationView==='explain')return;return showExplanation();});
$('explain-turn').addEventListener('click',showExplanation);
$('advanced-controls').addEventListener('toggle',()=>{requestAnimationFrame(()=>{prepareBrain();update();});});
$('comparison-panel').addEventListener('toggle',()=>{requestAnimationFrame(()=>{prepareBrain();update();});});

function showSpeed(){
  $('speed').textContent=`${speed}× playback`;
  $('speed').setAttribute('aria-label',`Simulation display speed ${speed} times. Change speed.`);
}
function cancelTurnReplay(){if(bundle?.turn_replay){speed=bundle.turn_replay.previous_speed;delete bundle.turn_replay;showSpeed();}}
const jumpToMemory=replayMemory;
replayMemory=function(){
  if(!window.WEBINAR_PRESENTATION||!bundle?.population){jumpToMemory();return;}
  const decision=shownDecision();if(!decision||!junctionEvidence(decision).applied)return;
  cancelTurnReplay();
  const end=bundle.hero.frames.find(f=>f.ms>decision.time&&!f.junction&&!f.deliberating);
  if(!end){jumpToMemory();return;}
  bundle.turn_replay={end_ms:end.ms,previous_speed:speed};
  elapsed=Math.max(0,(decision.capture_time??decision.time)-500);speed=1;showSpeed();
  playing=true;lastTime=0;lastEvidence='';$('pause').disabled=false;update();
  $('message').textContent='Replaying the recorded input and turn at normal speed.';
};
