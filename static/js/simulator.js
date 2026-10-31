import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { addGreenhouse, fitHouseView, resetHouseView } from "./greenhouse-model.js?v=demo-view-1";
import { createRenderScheduler } from "./render-scheduler.js";

const length = Number(JSON.parse(document.getElementById("greenhouse-length").textContent));
const width = Number(JSON.parse(document.getElementById("greenhouse-width").textContent));
const height = Number(JSON.parse(document.getElementById("greenhouse-height").textContent));
const basic = JSON.parse(document.getElementById("basic-sensors").textContent);
const recommended = JSON.parse(document.getElementById("recommended-sensors").textContent);
const candidates = JSON.parse(document.getElementById("candidate-sensors").textContent);
const recommendedNames = new Set(recommended.map(sensor => sensor.name));
const canvas = document.getElementById("greenhouse-canvas");
const frame = document.getElementById("scene-frame");
const loading = document.getElementById("scene-loading");
const scene = new THREE.Scene();
scene.background = new THREE.Color("#fff9f7");
const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.minDistance = Math.max(length, width, height) * 0.72;
controls.maxDistance = Math.max(length, width, height) * 4.5;
controls.target.set(length / 2, height * 0.37, 0);
const scheduler = createRenderScheduler({draw() {
  controls.update();
  renderer.render(scene, camera);
}});
controls.addEventListener('change', () => scheduler.invalidate());
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const sensorObjects = [];
function sensorColor(sensor) {
  return document.getElementById('scenario-select').value === 'recommended' && recommendedNames.has(sensor.name) ? 0xe1283d : 0x969a9f;
}

scene.add(new THREE.HemisphereLight(0xffffff, 0xe5ece5, 2.0));
const keyLight = new THREE.DirectionalLight(0xffffff, 2.1);
keyLight.position.set(-length, height * 2.5, width * 1.8);
keyLight.castShadow = true;
scene.add(keyLight);

function addLine(points, color, opacity = 1) {
  const geometry = new THREE.BufferGeometry().setFromPoints(points.map(([x, y, z]) => new THREE.Vector3(x, y, z)));
  const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }));
  scene.add(line);
  return line;
}

function createHouse() { addGreenhouse(THREE, scene, length, width, height, JSON.parse(document.getElementById("greenhouse-shape").textContent)); }

function updateDetail(sensor) {
  document.getElementById("detail-empty").hidden = true;
  document.getElementById("selected-sensor").hidden = false;
  document.getElementById("sensor-name").textContent = sensor.name;
  document.getElementById("sensor-x").textContent = `${sensor.x.toFixed(2)} m`;
  document.getElementById("sensor-y").textContent = `${sensor.y.toFixed(2)} m`;
  document.getElementById("sensor-z").textContent = `${sensor.z.toFixed(2)} m`;
  document.querySelector(".selected-dot").style.backgroundColor = `#${sensorColor(sensor).toString(16).padStart(6, "0")}`;
}

function renderSensors(sensors) {
  sensorObjects.forEach((marker) => {
    scene.remove(marker);
    marker.geometry.dispose();
    marker.material.dispose();
  });
  sensorObjects.length = 0;
  sensors.forEach((sensor, index) => {
    const material = new THREE.MeshStandardMaterial({
      color: sensorColor(sensor),
      emissive: sensorColor(sensor),
      emissiveIntensity: 0.12,
      roughness: 0.34,
    });
    const marker = new THREE.Mesh(new THREE.SphereGeometry(Math.max(width * 0.035, 0.12), 24, 18), material);
    marker.position.set(sensor.x, sensor.z, sensor.y - width / 2);
    marker.castShadow = true;
    marker.userData.sensor = sensor;
    scene.add(marker);
    sensorObjects.push(marker);
  });
  if (sensorObjects.length) updateDetail(sensorObjects[0].userData.sensor);
  scheduler.invalidate();
}

function resize() {
  const bounds = frame.getBoundingClientRect();
  const widthPx = Math.max(1, bounds.width);
  const heightPx = Math.max(1, bounds.height);
  renderer.setSize(widthPx, heightPx, false);
  camera.aspect = widthPx / heightPx;
  camera.updateProjectionMatrix();
  fitHouseView(THREE, camera, length, width, height);
  scheduler.invalidate();
}

function resetView() {
  resetHouseView(THREE, camera, controls, length, width, height);
}

createHouse();
renderSensors(document.getElementById("scenario-select").value === "recommended" ? candidates : basic);
resetView();
resize();
window.addEventListener("resize", resize);
document.getElementById("reset-view").addEventListener("click", resetView);
document.getElementById("scenario-select").addEventListener("change", (event) => {
  renderSensors(event.target.value === "recommended" ? candidates : basic);
});
renderer.domElement.addEventListener("pointerdown", (event) => {
  const bounds = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
  pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const intersection = raycaster.intersectObjects(sensorObjects)[0];
  if (intersection) updateDetail(intersection.object.userData.sensor);
});

let inViewport = true;
function updateActivity() { scheduler.setActive(inViewport && !document.hidden); }
const visibilityObserver = new IntersectionObserver(entries => {
  inViewport = entries[0].isIntersecting;
  updateActivity();
});
visibilityObserver.observe(frame);
document.addEventListener('visibilitychange', updateActivity);
window.addEventListener('pagehide', event => {
  if (event.persisted) {scheduler.setActive(false);return;}
  scheduler.dispose(); visibilityObserver.disconnect();
  document.removeEventListener('visibilitychange', updateActivity);
  controls.dispose(); renderer.dispose();
  scene.traverse(object => {
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(material => material?.dispose());
  });
});
window.addEventListener('pageshow', updateActivity);
scheduler.invalidate();
loading.hidden = true;
