/* Webinar controls use the same recorded frames and evidence as the workshop inspector. */
let population='live', hiveStatus={ready:[],state:'missing'}, selectionRequest=0;
const liveStart=start, liveSelectFly=selectFly;
const measured={live:{},hive:{}};
const populationRuns=new Map();
window.webinarOnBegin=data=>{if(!data.population){measured.live={...(data.cohort?.stages||{})};comparisonTable();}};
function drawPopulationGrid(){
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
  $('search-time-label').textContent=bundle.population?'Recorded search · ms':'Search · ms';
  const deadline=bundle.cohort?.deadline_ms??180000;
  $('seek').disabled=false;$('seek').max=String(bundle.streaming?bundle.buffer_ms:playbackEnd());$('seek').value=String(elapsed);
  $('seek-time').textContent=`${(elapsed/1000).toFixed(1)} / ${deadline/1000} s`;
  const hit=junctionEvidence(shownDecision()).hit;
  $('visible-provenance').textContent=hit?`${hit.payload.source_fly} observed “${hit.payload.outcome.replace('_',' ')}”. ${bundle.hero.owner} ${junctionEvidence(shownDecision()).applied?'uses that evidence.':'keeps both options.'}`:mode==='shared'?'Newcomers read completed A observations. Their own observations stay unpublished.':mode==='personal'?'Each fly can retrieve only its own completed observations.':'Each fly explores without external memory.';
  if(!bundle.streaming&&bundle.cohort?.summary){
    const summary=bundle.cohort.summary;
    if(measured[population][mode]!==summary){measured[population][mode]=summary;comparisonTable();if(summary.audit_errors?.length)$('message').textContent='Evidence audit failed. Inspect the raw results before presenting this run.';}
  }
};
$('seek').addEventListener('input',()=>{if(!bundle)return;elapsed=Number($('seek').value);playing=false;lastTime=0;$('pause').disabled=false;lastEvidence='';update();});

async function overview(condition){
  if(!populationRuns.has(condition)){
    const response=await fetch(`/api/hive/${condition}`);
    if(!response.ok){const error=await response.json();throw Error(error.detail||'The population is not ready.');}
    populationRuns.set(condition,await response.json());
  }
  return populationRuns.get(condition);
}
window.loadPopulationFly=async index=>{
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
start=async function(options={}){
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
      initial_memories:detail.initial_memories,memory_count:hiveStatus.memory_count,
      comparison_mode:'none',world,brain:data.brain,code:'Recorded population',
      cohort:{seeds:flies.map(r=>r.seed),deadline_ms:180000,summary:data.summary}});
    $('disconnect').hidden=true;$('run').textContent='Replay 1,000 flies';$('message').textContent='Recorded population. Each fly follows its own computed run.';
  }catch(error){
    bundle=previous;if(previous)mode=previous.mode;
    for(const button of document.querySelectorAll('.stage')){button.classList.toggle('selected',button.dataset.mode===mode);button.setAttribute('aria-pressed',String(button.dataset.mode===mode));}
    $('message').textContent=error.message;
  }finally{busy=false;$('run').disabled=false;$('computing').hidden=true;for(const button of document.querySelectorAll('.stage'))button.disabled=false;}
};
function choosePopulation(next){
  if(busy)return;
  population=next;playing=false;bundle=null;elapsed=0;mode='none';selectionRequest++;
  $('live-population').setAttribute('aria-pressed',String(next==='live'));
  $('hive-population').setAttribute('aria-pressed',String(next==='hive'));
  for(const button of document.querySelectorAll('.stage')){button.classList.toggle('selected',button.dataset.mode==='none');button.setAttribute('aria-pressed',String(button.dataset.mode==='none'));}
  $('disconnect').hidden=next==='hive';$('run').textContent=next==='hive'?'Play 1,000 flies':'Run eight flies';
  $('group-result').textContent=next==='hive'?'0/1,000':'0/8';$('fly-selector').replaceChildren();
  $('pause').disabled=true;$('seek').disabled=true;
  $('message').textContent=next==='hive'?'The population uses recorded, independently computed neural runs.':'Start No memory, then Personal memory, then Shared memory.';
  comparisonTable();lastEvidence='';update();
  $('population-ledger').hidden=next!=='hive';
}
$('population-grid').addEventListener('click',event=>{if(!bundle?.population)return;const box=$('population-grid').getBoundingClientRect(),columns=50,rows=Math.ceil(bundle.flies.length/columns),index=Math.floor((event.clientY-box.top)/box.height*rows)*columns+Math.floor((event.clientX-box.left)/box.width*columns);if(index>=0&&index<bundle.flies.length){$('population-fly').value=String(index);selectFly(index);}});
$('live-population').addEventListener('click',()=>choosePopulation('live'));
$('hive-population').addEventListener('click',()=>choosePopulation('hive'));
async function refreshHive(){
  try{
    const response=await fetch('/api/hive/status');if(!response.ok)throw Error('Population status is unavailable.');
    hiveStatus=await response.json();
    const state=hiveStatus.state;
    $('hive-status').textContent=state==='ready'||state==='ready_with_failures'?'1,000 flies measured in all three conditions. Stopped attempts remain included.':state==='missing'?'Prepare the population before the webinar.':state==='computing'||state==='starting'?`${hiveStatus.done.toLocaleString()} / ${hiveStatus.total.toLocaleString()} trials computed · ${hiveStatus.mode||'starting'}`:state==='stale'?'Population source changed. Archive earlier artifacts and prepare again.':state==='audit_failed'?'Population evidence audit failed. Read compute.log.':`Population ${state}${hiveStatus.detail?`: ${hiveStatus.detail}`:''}.`;
    $('prepare-hive').hidden=state==='ready'||state==='ready_with_failures';$('prepare-hive').disabled=['computing','starting','stale','audit_failed'].includes(state);
    $('cancel-hive').hidden=!['computing','starting'].includes(state);
    $('hive-population').disabled=!hiveStatus.ready.includes('none');
    measured.hive=hiveStatus.summary||{};if(population==='hive')comparisonTable();
  }catch(error){$('hive-status').textContent=error.message;}
}
$('prepare-hive').addEventListener('click',async()=>{try{const response=await fetch('/api/hive/prepare',{method:'POST'});if(!response.ok){const error=await response.json();throw Error(error.detail);}await refreshHive();}catch(error){$('hive-status').textContent=error.message;}});
$('cancel-hive').addEventListener('click',async()=>{try{const response=await fetch('/api/hive/cancel',{method:'POST'});if(!response.ok)throw Error('Preparation could not stop.');await refreshHive();}catch(error){$('hive-status').textContent=error.message;}});
ready.then(()=>{choosePopulation('live');refreshHive();setInterval(refreshHive,5000);});
