const dataNode = document.getElementById('location-data');
const panel = document.getElementById('location-scene');
const status = document.getElementById('location-loading');
const data = JSON.parse(dataNode.textContent);
let selected = new Set(data.selected);
let active = null;
let refreshMarkers = () => {};
let focusSensor = () => {};
let invalidate = () => {};
let disposeScene = () => {};
const retryButton = document.getElementById('location-retry');
if (retryButton) retryButton.addEventListener('click',()=>window.location.reload());

function failScene(error) {
  disposeScene();
  panel.dataset.sceneState = 'error';
  status.hidden = false;
  status.textContent = '3D를 표시하지 못했습니다. 좌표 목록은 계속 사용할 수 있습니다. 네트워크와 브라우저의 그래픽 가속 설정을 확인한 뒤 다시 불러오세요.';
  const retry = document.getElementById('location-retry');
  if (retry) retry.hidden = false;
  console.error('Greenhouse scene failed:', error);
}

// Selection still works in the coordinate list if WebGL or the CDN is unavailable.
function updateSelection(ids) {
  selected = new Set(ids);
  document.querySelectorAll('[data-combination]').forEach(row => {
    const ids = data.combinations[row.dataset.combination];
    const same = ids.every(id => selected.has(id)) && selected.size === ids.length;
    row.classList.toggle('comparison-selected', same);
    row.querySelector('.combination-select').setAttribute('aria-pressed', String(same));
  });
  document.querySelectorAll('.location-select').forEach(button => button.setAttribute('aria-pressed', String(selected.has(button.dataset.sensor))));
  refreshMarkers();
  invalidate();
}
document.querySelectorAll('[data-combination]').forEach(row => row.addEventListener('click', () => updateSelection(data.combinations[row.dataset.combination])));
document.querySelectorAll('.location-select').forEach(button => button.addEventListener('click', () => {
  focusSensor(button.dataset.sensor);
}));
updateSelection(data.selected);
const scenarioSelect = document.getElementById('location-scenario');
if (scenarioSelect) scenarioSelect.addEventListener('change', () => {
  updateSelection(scenarioSelect.value === 'recommended' ? data.recommended : []);
});

async function start() {
  const imports = Promise.all([
    import('three'), import('three/addons/controls/OrbitControls.js'), import('./greenhouse-model.js?v=demo-view-1'), import('./render-scheduler.js')
  ]);
  let timeout;
  const [THREE, {OrbitControls}, {addGreenhouse, toScene, fitHouseView, resetHouseView}, {createRenderScheduler}] = await Promise.race([
    imports,
    new Promise((_, reject) => {timeout = setTimeout(() => reject(new Error('3D module loading timed out')), 15000);}),
  ]).finally(() => clearTimeout(timeout));
  const canvas = document.getElementById('location-canvas');
  const tooltip = document.getElementById('location-tooltip');
  const {length, width, height} = data;
  const size = Math.max(length,width,height);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#fff9f7');
  const camera = new THREE.PerspectiveCamera(40,1,.01,Math.max(1000,size*20));
  const renderer = new THREE.WebGLRenderer({canvas,antialias:true});
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  renderer.setPixelRatio(pixelRatio);
  const controls = new OrbitControls(camera, canvas);
  controls.minDistance = size*.5;
  controls.maxDistance = size*5;
  controls.enableDamping = false;
  controls.target.set(length/2,height*.4,0);
  scene.add(new THREE.HemisphereLight(0xffffff,0xcbd9e2,2));
  const light = new THREE.DirectionalLight(0xffffff,2);
  light.position.set(-length,height*3,width*2);
  scene.add(light);
  addGreenhouse(THREE,scene,length,width,height,data.shape);
  const markers = [];
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  function showInfo(sensor, x=12, y=12) {
    active = sensor.name;
    tooltip.hidden = false;
    tooltip.textContent = `${sensor.name}\n길이 방향(X) ${sensor.x.toFixed(2)} m / ${sensor.relative[0]}%\n폭 방향(Y) ${sensor.y.toFixed(2)} m / ${sensor.relative[1]}%\n설치 높이(Z) ${sensor.z.toFixed(2)} m / ${sensor.relative[2]}%`;
    tooltip.style.left = `${Math.max(4,Math.min(x+12,panel.clientWidth-tooltip.offsetWidth-4))}px`;
    tooltip.style.top = `${Math.max(4,Math.min(y+12,panel.clientHeight-tooltip.offsetHeight-4))}px`;
    const detail = document.getElementById('location-detail');
    if (detail) {
      detail.hidden = false;
      document.getElementById('location-detail-empty').hidden = true;
      document.getElementById('location-sensor-name').textContent = sensor.name;
      for (const axis of ['x','y','z']) document.getElementById('location-sensor-'+axis).textContent = `${sensor[axis].toFixed(2)} m`;
      detail.querySelector('.selected-dot').style.backgroundColor = selected.has(sensor.name) ? '#e1283d' : '#969a9f';
    }
    refreshMarkers();
    invalidate();
  }
  for (const sensor of data.sensors.filter(sensor => sensor.position_valid)) {
    const marker = new THREE.Mesh(new THREE.SphereGeometry(size*.013*.8*Math.cbrt(0.5),16,12),new THREE.MeshStandardMaterial({color:0xc83e59,roughness:.5}));
    marker.position.copy(toScene(THREE,sensor,width));
    marker.userData.sensor = sensor;
    scene.add(marker);
    markers.push({marker,sensor});
  }

  refreshMarkers = () => {
    for (const {marker,sensor} of markers) {
      const chosen = selected.has(sensor.name);
      marker.material.color.set(chosen ? '#e1283d' : '#969a9f');
      marker.scale.setScalar(sensor.name===active ? 1.4 : chosen ? 1.2 : 1);
    }
    invalidate();
  };
  focusSensor = name => {
    const item = markers.find(item => item.sensor.name===name);
    if (item) showInfo(item.sensor);
    else {
      tooltip.hidden=false;
      tooltip.textContent = `${name}: 설치 위치 미등록 또는 온실 크기 범위 오류. 좌표 목록을 확인해 주세요.`;
      tooltip.style.left='8px'; tooltip.style.top='8px';
    }
  };
  const hitTargets = markers.map(item => item.marker);
  function pointAt(event) {
    const bounds=canvas.getBoundingClientRect();
    pointer.set((event.clientX-bounds.left)/bounds.width*2-1,-(event.clientY-bounds.top)/bounds.height*2+1);
    raycaster.setFromCamera(pointer,camera);
    const hit=raycaster.intersectObjects(hitTargets)[0];
    if (hit) showInfo(hit.object.userData.sensor,event.clientX-bounds.left,event.clientY-bounds.top);
    else {tooltip.hidden=true;}
  }
  canvas.addEventListener('pointermove',pointAt);
  canvas.addEventListener('click',pointAt);
  canvas.addEventListener('pointerleave',()=>{tooltip.hidden=true;});
  panel.addEventListener('keydown',event=>{if(event.key==='Escape') tooltip.hidden=true;});
  let viewReady = false;
  function fitView() {
    if (!viewReady) return;
    fitHouseView(THREE,camera,length,width,height);
  }
  const reset = () => {
    resetHouseView(THREE,camera,controls,length,width,height);
    viewReady = true; fitView(); invalidate();
  };
  document.getElementById('location-reset').addEventListener('click',reset);
  const scheduler = createRenderScheduler({draw() {
    try { render(); } catch (error) { failScene(error); }
  }});
  invalidate = () => scheduler.invalidate();
  let lastWidth = 0;
  let lastHeight = 0;
  function resize() {
    // The canvas is absolute: drawing-buffer dimensions cannot grow its parent.
    const widthPx = Math.max(1, Math.floor(panel.clientWidth));
    const heightPx = Math.max(1, Math.floor(panel.clientHeight));
    if (widthPx === lastWidth && heightPx === lastHeight) return;
    lastWidth = widthPx; lastHeight = heightPx;
    renderer.setSize(widthPx, heightPx, false);
    camera.aspect = widthPx / heightPx;
    camera.updateProjectionMatrix();
    fitView();
    invalidate();
  }
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(panel);
  let inViewport = true;
  const updateActivity = () => scheduler.setActive(inViewport && !document.hidden);
  const intersectionObserver = new IntersectionObserver(entries => {
    inViewport = entries[0].isIntersecting;
    updateActivity();
  });
  intersectionObserver.observe(panel);
  document.addEventListener('visibilitychange',updateActivity);
  controls.addEventListener('change',invalidate);
  canvas.addEventListener('webglcontextlost',event => {
    event.preventDefault();
    failScene(new Error('WebGL context lost'));
  });
  disposeScene = () => {
    scheduler.dispose();
    resizeObserver.disconnect(); intersectionObserver.disconnect();
    document.removeEventListener('visibilitychange',updateActivity);
    controls.removeEventListener('change',invalidate);
    controls.dispose();
    scene.traverse(object => {
      object.geometry?.dispose();
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach(material => material?.dispose());
    });
    renderer.dispose();
    invalidate = () => {};
    refreshMarkers = () => {};
  };
  window.addEventListener('pagehide',event => {
    if (event.persisted) scheduler.setActive(false);
    else disposeScene();
  });
  window.addEventListener('pageshow',updateActivity);
  function render() {
    renderer.render(scene,camera);
    if (panel.dataset.sceneState === 'loading') {
      panel.dataset.sceneState = 'ready';
      status.hidden = true;
    }
  }
  resize(); reset(); refreshMarkers(); updateActivity();
}
start().catch(failScene);
