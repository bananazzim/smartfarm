const root = document.getElementById('gso-fps');
if (root) {
  let current=JSON.parse(document.getElementById('gso-fps-data').textContent);
  const overview=root.querySelector('#fps-overview');
  const exploring=root.querySelector('#fps-exploring');
  const status=root.querySelector('#fps-load-status');
  const enterButton=root.querySelector('#enter-simulator');
  let api=null, timer=null, timeout=null, modulePromise=null, epoch=0, stopped=false;
  let historyTime=null, selected=null, selectedType='measured';

  function updateOverview() {
    const kinds={measured:new Set(),recommended:new Set()};
    for(const item of [...current.sensors,...current.records]) {
      const id=item.id ?? item.sensor_id;
      if(id==null)continue;
      const kind=(item.positionType ?? item.position_type)==='recommended'?'recommended':'measured';
      kinds[kind].add(String(id));
    }
    for(const kind of Object.keys(kinds))root.querySelector('#overview-'+kind).textContent=kinds[kind].size;
    root.querySelector('#overview-selected').textContent=(current.optimization?.recommendedIds || []).length;
    const label=current.optimization?.selectionLabel || '최적 조합 선정';
    const description=current.optimization?.error || (current.optimization?.recommendedIds?.length ? label+': '+current.optimization.recommendedIds.join(', ')+' · 분석 대상 '+current.optimization.sensorIds.length+'개 · 공통 시각 '+current.optimization.commonCount+'개' : '연결 가능한 최적 조합 결과가 없습니다.');
    root.querySelector('#optimization-status').textContent=description;
    root.querySelector('#active-combination').textContent=description;
    root.querySelector('#overview-title').textContent=current.config.name;
    root.querySelector('#overview-dim').textContent=`길이 ${current.config.length}m × 폭 ${current.config.width}m × 높이 ${current.config.height}m`;
  }
  async function readSnapshot() {
    if(!current.dataUrl || current.demo)return current;
    const response=await fetch(current.dataUrl,{credentials:'same-origin',headers:{Accept:'application/json'},cache:'no-store'});
    if(!response.ok)throw new Error('위치 데이터를 조회하지 못했습니다.');
    return response.json();
  }
  async function refresh() {
    if(stopped || document.hidden || root.dataset.view!=='exploring' || !api || api.getState().dead)return;
    const ticket=epoch;
    try {
      const next=await readSnapshot();
      if(ticket!==epoch || !api || JSON.stringify(next)===JSON.stringify(current))return;
      const pick=root.querySelector('#warn select');
      const at=historyTime ?? (pick?.value || next.at);
      if(JSON.stringify(next.config)!==JSON.stringify(current.config) && !api.setGreenhouseConfig(next.config))throw new Error('온실 규격을 표시할 수 없습니다.');
      api.setRecords(next.records,{at,staticSensors:next.sensors});
      current=next;updateOverview();
    } catch(error) {
      if(ticket!==epoch)return;
      const toast=root.querySelector('#toast');toast.textContent='새로고침하지 못해 기존 위치 표시를 유지합니다.';toast.classList.add('on');
    }
  }
  async function enter() {
    if(stopped || root.dataset.view==='exploring')return;
    const ticket=++epoch;
    root.dataset.view='exploring';overview.hidden=true;exploring.hidden=false;
    status.hidden=false;status.textContent='3D 온실을 불러오는 중…';
    exploring.scrollIntoView({block:'start'});
    timeout=setTimeout(()=>{if(ticket===epoch){status.hidden=false;status.textContent='연결이 지연되고 있습니다. 네트워크를 확인하거나 개요로 돌아가 다시 입장해 주세요.';}},20000);
    try {
      await new Promise(resolve=>requestAnimationFrame(resolve));
      modulePromise ??= import('./simulator-fps.js?v=combo-8');
      const [module,next]=await Promise.all([modulePromise,readSnapshot().catch(()=>current)]);
      if(stopped || ticket!==epoch)return;
      current=next;updateOverview();
      api=module.mountSimulator(root,{...current,at:historyTime ?? current.at});
      if(selected && api.getSensors().some(s=>s.id===selected&&s.positionType===selectedType))api.focusSensor(selected,selectedType,false);
      clearTimeout(timeout);status.hidden=true;
      if(current.issues.length)for(const issue of current.issues){const line=document.createElement('div');line.textContent=issue.code+': '+issue.message;root.querySelector('#warn').append(line);}
      timer=setInterval(refresh,15000);
      root.querySelector('#cv').focus({preventScroll:true});
    } catch(error) {
      if(ticket!==epoch)return;
      clearTimeout(timeout);modulePromise=null;
      status.hidden=false;status.textContent='3D를 불러오지 못했습니다. '+error.message;
      console.error('[GSO FPS]',error);
    }
  }
  async function back() {
    ++epoch;clearInterval(timer);clearTimeout(timeout);
    if(api && !api.getState().dead) {
      const state=api.getState();
      if(state.at!==current.at)historyTime=state.at;
      selected=state.selected;selectedType=state.selectedType || 'measured';
    }
    if(document.fullscreenElement===root.querySelector("#stage"))try{await document.exitFullscreen();}catch(_){}
    api?.destroy();api=null;
    root.dataset.view='overview';exploring.hidden=true;overview.hidden=false;
    updateOverview();enterButton.focus({preventScroll:true});overview.scrollIntoView({block:'start'});
  }
  root.querySelector('#enter-preview').addEventListener('click',enter);
  enterButton.addEventListener('click',enter);
  root.querySelector('#back-overview').addEventListener('click',back);
  root.addEventListener('change',event=>{if(event.target.matches('#warn select'))historyTime=event.target.value;});
  root.addEventListener('gso:destroy',()=>{clearInterval(timer);clearTimeout(timeout);api=null;});
  window.addEventListener('pagehide',event=>{
    if(event.persisted)return;
    stopped=true;++epoch;clearInterval(timer);clearTimeout(timeout);api?.destroy();
  });
  updateOverview();
  if(current.autoEnter)enter();
}
