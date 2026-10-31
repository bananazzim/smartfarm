import * as THREE from 'three';
import {toNum, parseTime, roofAt, fromRecords, sensorKey} from './fps-data.js?v=1';
import {pointBlocked, clearSegment, planRoute} from './fps-navigation.js?v=ghost-5';
import {isSensorNear, labelPosition} from './fps-proximity.js?v=near-6';

export function mountSimulator(root, initial = {}) {
if (window.GSOSim && window.GSOSim.destroy) { try { window.GSOSim.destroy(); } catch (_) {} }
const T = THREE, $ = s => root.querySelector(s);
if (!initial.config || ![initial.config.length,initial.config.width,initial.config.height].every(v=>Number.isFinite(v)&&v>=3)) throw new Error("1인칭 온실 규격은 길이·폭·높이가 각각 3m 이상이어야 합니다.");
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const EYE = 1.6, RAD = 0.32;
let cfg = { name: "DEMO", length: 30, width: 7, height: 4 };

/* 연구 좌표계(x 길이, y 폭, z 높이, m) -> Three(X, Y-up, Z). 기존 GSO toScene과 동일 방향 */
const toThree = (x, y, z) => new T.Vector3(x, z, y);

/* ---------- 렌더러 / 씬 ---------- */
const stage = $("#stage"), cv = $("#cv");
const renderer = new T.WebGLRenderer({ canvas: cv, antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap; renderer.shadowMap.autoUpdate = false;
const scene = new T.Scene(); scene.background = new T.Color(0xcfdadf); scene.fog = new T.Fog(0xd3dcdc, 55, 150);
const cam = new T.PerspectiveCamera(70, 1, 0.05, 300); cam.rotation.order = "YXZ";
scene.add(new T.HemisphereLight(0xf0f1ea, 0x7a7f66, 2.0));
const sun = new T.DirectionalLight(0xfff4e2, 2.5); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004;
scene.add(sun, sun.target);
const markerRoot = new T.Group(); scene.add(markerRoot);
let world = null, rects = [], npcs = [];

const M = (c, o) => new T.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.88, flatShading: true }, o || {}));
const E = new T.Euler(), Q = new T.Quaternion(), V = new T.Vector3(), S3 = new T.Vector3();
const mk = (x, y, z, ry = 0, rz = 0, sx = 1, sy = sx, sz = sx) => { E.set(0, ry, rz, "YZX"); return new T.Matrix4().compose(V.set(x, y, z), Q.setFromEuler(E), S3.set(sx, sy, sz)); };
const rng = a => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
function inst(geo, mat, items, cast = true) {
  const m = new T.InstancedMesh(geo, mat, items.length);
  items.forEach((it, i) => { m.setMatrixAt(i, it.m); if (it.c) m.setColorAt(i, it.c); });
  m.castShadow = cast; m.receiveShadow = true; m.frustumCulled = false; m.instanceMatrix.needsUpdate = true; return m;
}
const disposeTree = o => {if(!o)return;const geometries=new Set(),materials=new Set();o.traverse(c=>{if(c.geometry)geometries.add(c.geometry);if(c.material)[].concat(c.material).forEach(m=>materials.add(m));if(c.isInstancedMesh&&c.dispose)c.dispose();});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());};

/* ---------- 온실 구성 ---------- */
function build() {
  if (world) { scene.remove(world); disposeTree(world); }
  const { length: L, width: W, height: H } = cfg, g = world = new T.Group(); scene.add(g);
  const wallH = H * 0.45, arc = H - wallH, DH = 2.3, DW = 1.4, N = 24;
  const prof = []; for (let i = 0; i <= N; i++) { const t = Math.PI * i / N; prof.push([W / 2 - W / 2 * Math.cos(t), wallH + arc * Math.sin(t)]); }
  const wood = M(0xa9aea6), bedWood = M(0x8c8a7c), film = M(0xeef1ec, { transparent: true, opacity: 0.3, roughness: 0.3, side: T.DoubleSide, depthWrite: false, flatShading: false });
  const add = (geo, mat, x, y, z, o = {}) => { const m = new T.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = !!o.cast; m.receiveShadow = o.recv !== false; if (o.rz) m.rotation.z = o.rz; g.add(m); return m; };

  // 지면 슬래브 + 출입 통로
  const grass = M(0x7a8f54), dirt = M(0x5f4c3a);
  add(new T.PlaneGeometry(600, 600), M(0x7f9159), L / 2, -0.06, W / 2).rotation.x = -Math.PI / 2;
  const slab = add(new T.BoxGeometry(L + 34, 0.6, W + 30), [dirt, dirt, grass, dirt, dirt, dirt], L / 2 - 8, -0.3, W / 2);
  add(new T.BoxGeometry(14, 0.03, 1.9), M(0xbdb59d), -7, 0.012, W / 2);
  add(new T.BoxGeometry(L, 0.03, W), M(0x8f8a76), L / 2, 0.01, W / 2);
  add(new T.BoxGeometry(L, 0.04, 1.5), M(0xa7a28e), L / 2, 0.03, W / 2);

  // 아치 골조
  const pts = [[0, 0], [0, wallH / 2], ...prof, [W, wallH / 2], [W, 0]].map(p => new T.Vector3(0, p[1], p[0]));
  const rib = new T.TubeGeometry(new T.CatmullRomCurve3(pts, false, "centripetal"), 72, 0.06, 5, false);
  const n = Math.max(2, Math.round(L / 2.5) + 1);
  g.add(inst(rib, wood, Array.from({ length: n }, (_, i) => ({ m: mk(L * i / (n - 1), 0, 0) }))));
  const rod = new T.CylinderGeometry(0.03, 0.03, L, 5);
  [0, 4, 8, 12, 16, 20, 24].forEach(i => add(rod, wood, L / 2, prof[i][1], prof[i][0], { cast: true, rz: Math.PI / 2 }));
  [0, W].forEach(z => add(new T.BoxGeometry(L, 0.14, 0.09), wood, L / 2, 0.07, z, { cast: true }));

  // 피복(비닐) — 측면/지붕 + 양 끝 벽
  const prow = [[0, 0], ...prof, [W, 0]], pos = [], idx = [];
  prow.forEach((p, i) => { pos.push(0, p[1], p[0], L, p[1], p[0]); if (i < prow.length - 1) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); } });
  const fg = new T.BufferGeometry(); fg.setAttribute("position", new T.Float32BufferAttribute(pos, 3)); fg.setIndex(idx); fg.computeVertexNormals();
  add(fg, film, 0, 0, 0, { recv: false }).renderOrder = 2;
  const endShape = door => { const s = new T.Shape(); s.moveTo(0, 0); if (door) { s.lineTo(W / 2 - DW / 2, 0); s.lineTo(W / 2 - DW / 2, DH); s.lineTo(W / 2 + DW / 2, DH); s.lineTo(W / 2 + DW / 2, 0); } s.lineTo(W, 0); for (let i = N; i >= 0; i--) s.lineTo(prof[i][0], prof[i][1]); s.closePath(); return new T.ShapeGeometry(s); };
  [[0, true], [L, false]].forEach(([x, d]) => { const m = add(endShape(d), film, x, 0, 0, { recv: false }); m.rotation.y = -Math.PI / 2; m.renderOrder = 2; });

  // 측면 환기창 + 출입문
  [0.012, W - 0.012].forEach(z => {
    add(new T.PlaneGeometry(L, 0.6), M(0xe6ebde, { transparent: true, opacity: 0.42, side: T.DoubleSide, depthWrite: false }), L / 2, 1.15, z, { recv: false }).renderOrder = 3;
    [0.85, 1.45].forEach(y => add(new T.BoxGeometry(L, 0.05, 0.07), wood, L / 2, y, z, { cast: true }));
    add(rod, M(0xfff8e8, { transparent: true, opacity: 0.8 }), L / 2, 1.52, z, { rz: Math.PI / 2 }).scale.set(1.7, 1, 1.7);
  });
  [W / 2 - DW / 2, W / 2 + DW / 2].forEach(z => add(new T.BoxGeometry(0.09, DH, 0.09), wood, 0, DH / 2, z, { cast: true }));
  add(new T.BoxGeometry(0.09, 0.09, DW + 0.09), wood, 0, DH, W / 2, { cast: true });
  const door = new T.Group(); door.position.set(0, 0, W / 2 + DW / 2 - 0.04); door.rotation.y = 1.75; g.add(door);
  const dw = DW - 0.1, dh = DH - 0.08;
  const dp = new T.Mesh(new T.PlaneGeometry(dw, dh), film); dp.rotation.y = Math.PI / 2; dp.position.set(0, dh / 2 + 0.02, -dw / 2); door.add(dp);
  [[0, dh / 2, 0, 0.06, dh, 0.06], [0, dh / 2, -dw, 0.06, dh, 0.06], [0, dh, -dw / 2, 0.06, 0.06, dw], [0, 0.04, -dw / 2, 0.06, 0.06, dw], [0, dh / 2, -dw / 2, 0.05, 0.04, dw]].forEach(a => { const b = new T.Mesh(new T.BoxGeometry(a[3], a[4], a[5]), wood); b.position.set(a[0], a[1], a[2]); b.castShadow = true; door.add(b); });

  // 재배 베드 + 지지대
  rects = []; const rnd = rng(7), bedRows = [];
  [-1, 1].forEach(s => {
    const bz = W / 2 + s * 1.7;
    add(new T.BoxGeometry(L - 1, 0.28, 1.1), bedWood, L / 2, 0.14, bz, { cast: true });
    const nt = Math.max(1, Math.floor((L - 1.2) / 2.4)), tl = (L - 1.2) / nt;
    g.add(inst(new T.BoxGeometry(tl - 0.18, 0.06, 0.9), M(0xffffff), Array.from({ length: nt }, (_, i) => ({ m: mk(0.6 + tl * (i + 0.5), 0.29, bz), c: new T.Color(0x5a4535).offsetHSL(0, 0, (rnd() - 0.5) * 0.06) })), false));
    rects.push([0.5 - RAD, bz - 0.55 - RAD, L - 0.5 + RAD, bz + 0.55 + RAD]);
    [0.55, L / 2, L - 0.55].forEach(x => { add(new T.CylinderGeometry(0.03, 0.03, 2.85, 5), wood, x, 1.42, bz, { cast: true }); add(new T.BoxGeometry(0.05, 0.05, 0.7), wood, x, 2.82, bz, { cast: true }); });
    [-1, 1].forEach(r => { bedRows.push(bz + r * 0.22); add(rod, M(0xbfc4c0, { metalness: 0.5, roughness: 0.4 }), L / 2, 2.75, bz + r * 0.22, { rz: Math.PI / 2 }).scale.set(0.3, 1, 0.3); });
  });

  // 토마토 식물 (InstancedMesh)
  const plants = [];
  bedRows.forEach((bz, ri) => { for (let x = 1.4 + (ri % 2) * 0.27; x <= L - 1.4; x += 0.55) plants.push({ x, z: bz + (rnd() - 0.5) * 0.05, h: 1.9 + rnd() * 0.5, ry: rnd() * 6.28, lean: (rnd() - 0.5) * 0.1 }); });
  const stems = [], leaves = [], fruits = [], calyx = [], flowers = [], strings = [];
  const blades = [mk(0.3, 0, 0), mk(0.2, 0, 0.11, -0.8, 0, 0.62), mk(0.2, 0, -0.11, 0.8, 0, 0.62)];
  const greens = [0x58773a, 0x5f8040, 0x4b6c34, 0x6a8a45], palette = [[0xb83a2e, 0xaa3328], [0xc2452d, 0xb83a2e, 0xc9693a], [0xc98a3c, 0x8fa24f], [0x7c9a4b, 0x73914a]];
  plants.forEach(p => {
    const Pm = mk(p.x, 0, p.z, p.ry, p.lean);
    stems.push({ m: Pm.clone().multiply(mk(0, 0, 0, 0, 0, 1, p.h, 1)), c: new T.Color(0x6a8847).offsetHSL(0, 0, (rnd() - 0.5) * 0.06) });
    const nL = 9;
    for (let k = 0; k < nL; k++) {
      const f = k / (nL - 1), size = (1.15 - 0.45 * f) * (0.85 + rnd() * 0.3), base = Pm.clone().multiply(mk(0, p.h * (0.26 + 0.7 * f), 0, k * 2.4 + rnd() * 0.3, -0.2 - rnd() * 0.35 + f * 0.25, size));
      const col = new T.Color(greens[Math.floor(rnd() * 4)]).offsetHSL(0, 0, (rnd() - 0.5) * 0.06);
      blades.forEach(b => leaves.push({ m: base.clone().multiply(b), c: col }));
    }
    const nT = 3 + (rnd() > 0.5 ? 1 : 0);
    for (let t = 0; t < nT; t++) {
      const hh = p.h * (0.36 + 0.14 * t), ang = rnd() * 6.28, r0 = 0.12 + rnd() * 0.06, nF = 3 + Math.floor(rnd() * 3), pal = palette[Math.min(t, 3)];
      for (let i = 0; i < nF; i++) {
        const rad = 0.042 + rnd() * 0.012, ox = Math.cos(ang) * r0 + (rnd() - 0.5) * 0.1, oz = Math.sin(ang) * r0 + (rnd() - 0.5) * 0.1, oy = hh - 0.05 * i - rnd() * 0.04;
        fruits.push({ m: Pm.clone().multiply(mk(ox, oy, oz, 0, 0, rad)), c: new T.Color(pal[Math.floor(rnd() * pal.length)]).offsetHSL(0, 0, (rnd() - 0.5) * 0.05) });
        calyx.push({ m: Pm.clone().multiply(mk(ox, oy + rad * 0.85, oz, rnd() * 3, 0, rad * 0.6, rad * 0.22, rad * 0.6)) });
      }
    }
    for (let i = 0; i < 2; i++) flowers.push({ m: Pm.clone().multiply(mk((rnd() - 0.5) * 0.12, p.h * (0.96 + 0.03 * i), (rnd() - 0.5) * 0.12, 0, 0, 0.03)) });
    strings.push({ m: mk(p.x, 0.3, p.z, 0, 0, 1, 2.45, 1) });
  });
  g.add(
    inst(new T.CylinderGeometry(0.013, 0.021, 1, 5).translate(0, 0.5, 0), M(0xffffff), stems),
    inst(new T.OctahedronGeometry(1, 0).scale(0.3, 0.025, 0.12), M(0xffffff, { side: T.DoubleSide }), leaves),
    inst(new T.IcosahedronGeometry(1, 1), M(0xffffff, { roughness: 0.55 }), fruits),
    inst(new T.OctahedronGeometry(1, 0), M(0x4b6c34), calyx, false),
    inst(new T.IcosahedronGeometry(1, 0), M(0xe0c258), flowers, false),
    inst(new T.CylinderGeometry(0.004, 0.004, 1, 3).translate(0, 0.5, 0), M(0xf4efe0), strings, false)
  );

  // 주변 나무
  const trees = [], r2 = rng(21);
  for (let i = 0; i < 26; i++) { const x = -24 + r2() * (L + 30), z = -13 + r2() * (W + 26); if (x > -6 && x < L + 6 && z > -5 && z < W + 5) continue; trees.push({ x, z, s: 0.8 + r2() * 0.8, c: new T.Color(0x5f7a45).offsetHSL((r2() - 0.5) * 0.04, 0, (r2() - 0.5) * 0.1) }); }
  g.add(inst(new T.CylinderGeometry(0.15, 0.2, 1.4, 5).translate(0, 0.7, 0), M(0x6f5a45), trees.map(t => ({ m: mk(t.x, 0, t.z, 0, 0, t.s) }))),
        inst(new T.IcosahedronGeometry(1.4, 0), M(0xffffff), trees.map(t => ({ m: mk(t.x, 2.3 * t.s, t.z, t.x, 0, t.s, t.s * 1.15, t.s), c: t.c }))));

  // 먼 배경: 파스텔 저폴리 마을
  const r3 = rng(5), bl = [], rf = [], bpal = [0xcdb9a8, 0xb5bfb3, 0xd3c6ad, 0xb8c1c8, 0xc3b0a6];
  for (let i = 0; i < 16; i++) {
    const a = i / 16 * 6.283 + r3() * 0.3, bw = 6 + r3() * 4, bh = 8 + r3() * 8, bd = 6 + r3() * 4, bx = L / 2 + Math.cos(a) * (L / 2 + 48 + r3() * 10), bz = W / 2 + Math.sin(a) * (W / 2 + 46 + r3() * 10), bc = new T.Color(bpal[i % 5]), by = r3() * 0.5;
    bl.push({ m: mk(bx, bh / 2, bz, by, 0, bw, bh, bd), c: bc }); rf.push({ m: mk(bx, bh, bz, by, 0, bw, 2.5 + r3() * 2, bd), c: bc.clone().offsetHSL(0, -0.08, -0.2) });
  }
  g.add(inst(new T.BoxGeometry(1, 1, 1), M(0xffffff), bl, false), inst(new T.ConeGeometry(0.75, 1, 4).rotateY(Math.PI / 4).translate(0, 0.5, 0), M(0xffffff), rf, false));

  // 작업자 NPC (보기만 하는 배경 인물, 상호작용 없음)
  npcs = [];
  if (L >= 8 && W >= 4.5) {
    const lanes = [W / 2], sideHi = (W / 2 + 2.25 + W) / 2; if (W - W / 2 - 2.25 > 0.9) lanes.push(sideHi, W - sideHi);
    const looks = [{ shirt: 0x5d7f80, pants: 0x3d4650, hat: 0xcdb77d, skin: 0xe0b08e, basket: true }, { shirt: 0xa9715a, pants: 0x4d555c, hat: 0x66794f, skin: 0xc08a66 }, { shirt: 0x7b8ea8, pants: 0x464a54, hat: 0xcfcab9, skin: 0xe8bf9f }];
    lanes.slice(0, 3).forEach((lz, i) => npcs.push(makeWorker(g, looks[i], lz, clamp([12, 20, 8][i] * L / 30, 2.5, L - 2), [1, -1, 1][i], [0.9, 0.7, 0.8][i], L, rnd)));
  }

  // 조명 범위
  const h = Math.max(L, W) / 2 + 14; sun.position.set(L / 2 - 10, 30, W / 2 + 16); sun.target.position.set(L / 2, 0, W / 2); sun.target.updateMatrixWorld();
  Object.assign(sun.shadow.camera, { left: -h, right: h, top: h, bottom: -h, near: 1, far: 90 }); sun.shadow.camera.updateProjectionMatrix();
  renderer.shadowMap.needsUpdate = true;
  $("#ghName").textContent = cfg.name; $("#ghName").hidden = !cfg.name; $("#ghDim").textContent = `길이 ${L} m × 폭 ${W} m × 높이 ${H} m · 단동 비닐온실`;
}

/* ---------- 작업자 NPC ---------- */
function makeWorker(parent, o, z, x, dir, sp, L, rnd) {
  const g = new T.Group(), mt = c => M(c), box = (w, h, d, c, px, py, pz) => { const m = new T.Mesh(new T.BoxGeometry(w, h, d), mt(c)); m.position.set(px, py, pz); return m; };
  const limb = (w, h, c, py, pz, hand) => { const p = new T.Group(); p.position.set(0, py, pz); p.add(box(w, h, w, c, 0, -h / 2, 0)); if (hand) { const s = new T.Mesh(new T.IcosahedronGeometry(0.06, 0), mt(hand)); s.position.y = -h - 0.03; p.add(s); } g.add(p); return p; };
  const legs = [-1, 1].map(s => limb(0.14, 0.82, o.pants, 0.82, s * 0.09)), arms = [-1, 1].map(s => limb(0.11, 0.5, o.shirt, 1.36, s * 0.25, o.skin));
  g.add(box(0.26, 0.56, 0.4, o.shirt, 0, 1.1, 0), box(0.03, 0.4, 0.3, 0xf1ede0, 0.145, 1.02, 0));
  const head = new T.Mesh(new T.IcosahedronGeometry(0.14, 1), mt(o.skin)); head.position.y = 1.56; g.add(head);
  const brim = new T.Mesh(new T.CylinderGeometry(0.27, 0.27, 0.025, 10), mt(o.hat)), crown = new T.Mesh(new T.CylinderGeometry(0.14, 0.16, 0.12, 8), mt(o.hat)); brim.position.y = 1.67; crown.position.y = 1.72; g.add(brim, crown);
  if (o.basket) { const b = new T.Group(); b.add(box(0.3, 0.16, 0.24, 0xb98b57, 0, 0, 0)); for (let i = 0; i < 5; i++) { const t = new T.Mesh(new T.IcosahedronGeometry(0.05, 0), mt(0xb03a2e)); t.position.set((i % 3 - 1) * 0.08, 0.1, (i % 2 - 0.5) * 0.1); b.add(t); } b.position.set(0.3, 0.88, 0); g.add(b); }
  g.traverse(c => { c.castShadow = false; });
  const blob = new T.Mesh(new T.CircleGeometry(0.38, 14), new T.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.22, depthWrite: false })); blob.rotation.x = -Math.PI / 2; blob.position.y = 0.065;
  const root = new T.Group(); root.position.set(x, 0, z); root.add(g, blob); parent.add(root);
  return { root, g, legs, arms, x, z, dir, sp, minX: 2.5, maxX: L - 2, yaw: dir > 0 ? 0 : Math.PI, state: "walk", timer: 0, face: 1, ph: rnd() * 6, stopX: clamp(x + dir * (4 + rnd() * 6), 2.5, L - 2) };
}
function stepNpc(n, dt) {
  let f = 1, goal = n.dir > 0 ? 0 : Math.PI;
  if (n.state === "tend") {
    n.timer -= dt; n.ph += dt * 4; goal = Math.atan2(-n.face, 0); f = 0;
    if (n.timer <= 0) { n.state = "walk"; if ((n.dir > 0 && n.x >= n.maxX - 0.01) || (n.dir < 0 && n.x <= n.minX + 0.01)) n.dir = -n.dir; n.stopX = clamp(n.x + n.dir * (4 + Math.random() * 6), n.minX, n.maxX); }
  } else {
    if (f && n.dir * (n.x - n.stopX) >= 0) { n.state = "tend"; n.timer = 3.5 + Math.random() * 2.5; const c = cfg.width / 2; n.face = n.z < c - 0.2 ? 1 : n.z > c + 0.2 ? -1 : (Math.random() > 0.5 ? 1 : -1); f = 0; }
  }
  if (f) { n.x = clamp(n.x + n.dir * n.sp * dt, n.minX, n.maxX); n.ph += n.sp * dt * 5.5; }
  n.yaw += angDiff(n.yaw, goal) * Math.min(1, dt * 6); n.g.rotation.y = n.yaw;
  const sw = f ? Math.sin(n.ph) * 0.6 : 0, td = n.state === "tend";
  n.legs[0].rotation.z = sw; n.legs[1].rotation.z = -sw;
  n.arms[0].rotation.z = td ? 1.3 + 0.15 * Math.sin(n.ph) : -sw * 0.8; n.arms[1].rotation.z = td ? 0.9 + 0.15 * Math.sin(n.ph + 1.5) : sw * 0.8;
  n.g.position.y = f ? Math.abs(Math.sin(n.ph)) * 0.03 : 0; n.root.position.set(n.x, 0, n.z);
}

/* ===== 순수 함수: 측정 기록 -> 센서 위치 (DOM/THREE/cfg 비의존) ===== */

function whyBad(s, seen) {
  const L = cfg.length, W = cfg.width, H = cfg.height;
  if (!s.id) return "센서 ID가 없습니다"; if (seen.has(s.key)) return "중복된 센서 ID입니다";
  if (![s.x, s.y, s.z].every(Number.isFinite)) return "좌표가 없거나 숫자가 아닙니다";
  if (s.x < 0 || s.x > L) return `x=${s.x}가 온실 길이(0~${L} m) 밖입니다`;
  if (s.y < 0 || s.y > W) return `y=${s.y}가 온실 폭(0~${W} m) 밖입니다`;
  if (s.z < 0 || s.z > H) return `z=${s.z}가 온실 높이(0~${H} m) 밖입니다`;
  const rh = roofAt(s.y, cfg); if (s.z > rh + 1e-6) return `피복재 밖입니다 (y=${s.y} 위치의 지붕 높이는 ${rh.toFixed(2)} m)`;
  return "";
}
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
function sensorDescription(s) { return (s.positionType === 'recommended' ? '추천 후보 위치' : '실제 설치') + (s.isRecommended === true ? (initial.optimization?.selectedRank > 1 ? ' · 비교 조합 포함' : ' · 최적 조합 선정') : ''); }
function setLabel(o, s) { const lb = o.lb;lb.style.setProperty('--sensor-color',o.rec?'#2979FF':'#78838D');lb.style.setProperty('--sensor-outline',o.rec?'#153A80':'#78838D'); lb.textContent = ""; lb.append(el("b", "", s.id), el("i", "", sensorDescription(s) + (s.isRecommended === true ? '' : (initial.optimization?.selectedRank > 1 ? ' · 비교 조합 미포함' : ' · 최적 조합 미선정'))), el("em", "", "높이 " + s.z.toFixed(2) + " m"), el("small", "coords", `x ${s.x.toFixed(2)} · y ${s.y.toFixed(2)} · z ${s.z.toFixed(2)} m`)); }
function renderIssues() {
  const w = $("#warn"); w.textContent = "";
  const all = adapterIssues.map(i => ({ id: i.id || (i.row ? "행 " + i.row : "입력"), msg: i.code+": "+i.message })).concat(rejected);
  all.slice(0, 6).forEach(i => w.append(el("div", "", i.id + ": " + i.msg)));
  if (all.length > 6) w.append(el("div", "", "외 " + (all.length - 6) + "건"));
  if (histTimes.length) { const sel = el("select"); sel.setAttribute("aria-label", "측정 시점 선택"); sel.append(new Option("측정 시점 선택…", ""));const options=[...histTimes];const canonical=Number.isFinite(parseTime(lastAt))?new Date(parseTime(lastAt)).toISOString():"";if(canonical&&!options.includes(canonical))options.push(canonical);options.sort().forEach(t => sel.append(new Option(new Date(t).toLocaleString("ko-KR", {timeZone:"Asia/Seoul"}), t))); sel.value = canonical; sel.onchange = () => api.setTime(sel.value); w.append(sel); }
}

/* ---------- 센서 마커 ---------- */
const GEO = { core: new T.SphereGeometry(0.09, 20, 14), halo: new T.SphereGeometry(0.1, 12, 8), ring: new T.TorusGeometry(0.17, 0.011, 6, 28), leader: new T.CylinderGeometry(0.006, 0.006, 1, 4).translate(0, 0.5, 0), foot: new T.RingGeometry(0.1, 0.17, 24) };
const markerMaterials = (color,emissive) => ({core:new T.MeshStandardMaterial({color,emissive,roughness:.35}),halo:new T.MeshBasicMaterial({color,transparent:true,opacity:.2,depthTest:false,depthWrite:false}),ring:new T.MeshBasicMaterial({color}),leader:new T.MeshBasicMaterial({color,transparent:true,opacity:.55}),foot:new T.MeshBasicMaterial({color,transparent:true,opacity:.6,side:T.DoubleSide})});
const MAT = {measured:markerMaterials(0x78838D,0x20252a),recommended:markerMaterials(0x2979FF,0x153A80)};
MAT.recommended.ring.color.setHex(0x153A80);
const markers = new Map(); let sensors = [], rawSensors = [], rejected = [], selId = null, lastRecords = null, lastAt = "", adapterIssues = [], histTimes = [], histories = {}, isDemo = false;
let staticSensors=[];
function makeMarker(s) {
  const g = new T.Group(), rec = s.isRecommended === true || s.positionType === "recommended";
  const materials=rec?MAT.recommended:MAT.measured;
  const core = new T.Mesh(GEO.core, materials.core), halo = new T.Mesh(GEO.halo, materials.halo), ring = new T.Mesh(GEO.ring, materials.ring), leader = new T.Mesh(GEO.leader, materials.leader), foot = new T.Mesh(GEO.foot, materials.foot);
  ring.rotation.x = Math.PI / 2; halo.renderOrder = 10; halo.userData.id = s.key; core.castShadow = false;
  foot.rotation.x = -Math.PI / 2; leader.visible = true;
  g.add(core, halo, ring, leader, foot);
  const lb = document.createElement("div"); lb.className = "lbl" + (rec ? " rec" : ""); $("#lbls").appendChild(lb);
  const o = { g, core, halo, ring, leader, foot, lb, rec }; place(o, s); return o;
}
function place(o, s) {
  o.g.position.copy(toThree(s.x, s.y, s.z)); o.leader.position.y = -s.z; o.leader.scale.y = s.z; o.foot.position.y = -s.z + 0.02;
  setLabel(o, s);
}
const num = toNum;
function setSensors(list) {
  rawSensors = Array.isArray(list) ? list : []; const { length: L, width: W, height: H } = cfg, seen = new Set(), next = []; rejected = [];
  const unique=new Map(),conflicts=new Set();
  rawSensors.forEach((r, i) => {
    const s = { id: r && r.id != null ? String(r.id).trim() : "", x: num(r && r.x), y: num(r && r.y), z: num(r && r.z), isRecommended: r?.isRecommended === true, positionType: r && (r.positionType ?? r.position_type) === "recommended" ? "recommended" : "measured" };
    s.key = sensorKey(s);
    if(unique.has(s.key)){const old=unique.get(s.key);if(['x','y','z'].some(a=>old[a]!==s[a]))conflicts.add(s.key);return;}
    unique.set(s.key,s);
  });
  [...unique.values()].forEach((s,i)=>{
    const why = conflicts.has(s.key) ? 'POSITION_CONFLICT: 같은 센서에 서로 다른 정적 좌표가 있습니다' : whyBad(s, seen);
    if (!why) { seen.add(s.key); next.push(s); } else rejected.push({ id: s.id || "#" + (i + 1), msg: why });
  });
  markers.forEach((o, id) => { const s = next.find(n => n.key === id); if (!s || (s.isRecommended === true || s.positionType === "recommended") !== o.rec) { markerRoot.remove(o.g); o.lb.remove(); markers.delete(id); } });
  next.forEach(s => { const o = markers.get(s.key); if (o) place(o, s); else { const m = makeMarker(s); markers.set(s.key, m); markerRoot.add(m.g); } });
  sensors = next; if (selId && !markers.has(selId)) selId = null; renderUI(); emit("issues", { rejected: rejected.map(r => ({ ...r })), adapter: adapterIssues.slice() });
}
function renderUI() {
  $("#cnt").textContent = sensors.length + "개 / 강조 " + sensors.filter(s=>s.isRecommended===true).length + "개";
  const list = $("#list"); list.textContent = ""; if (!sensors.length) list.append(el("div", "empty", "표시할 센서가 없습니다."));
  sensors.forEach(q => { const b = el("button", "item" + (q.key === selId ? " on" : "")), box = el("span"), rec = q.isRecommended === true || q.positionType === "recommended"; b.type = "button"; b.dataset.id = q.key;b.style.setProperty("--sensor-color",rec?"#2979FF":"#78838D");b.style.setProperty("--sensor-outline",rec?"#153A80":"#78838D"); box.append(el("b", "", q.id), el("small", "", `x ${q.x.toFixed(1)} · y ${q.y.toFixed(1)} · z ${q.z.toFixed(1)} m`)); b.append(el("span", "dot" + (rec ? " rec" : "")), box, el("span", "tag", sensorDescription(q))); list.append(b); });
  renderIssues(); $("#demoNote").hidden = !isDemo;
  const s = sensors.find(q => q.key === selId);
  const d = $("#detail"); d.textContent = "";
  if (!s) d.append(el("h2", "", "센서 상세"), el("div", "empty", "목록이나 화면의 센서 마커를 선택하세요."));
  else { const dl = el("dl"), go = el("button", "btn pri go", "센서 위치로 이동"); go.type = "button"; go.dataset.go = s.key; [["구분", s.positionType === "recommended" ? "추천 후보 위치" : "실제 설치 위치"], ["길이 방향 x", s.x.toFixed(2) + " m"], ["폭 방향 y", s.y.toFixed(2) + " m"], ["바닥 기준 높이 z", s.z.toFixed(2) + " m"]].forEach(([k, v]) => dl.append(el("dt", "", k), el("dd", "", v))); d.append(el("h2", "", "센서 " + s.id), dl, go); }
}
const emit = (n, d) => { try { stage.dispatchEvent(new CustomEvent("gso:" + n, { bubbles: true, detail: d })); } catch (_) {} };
function select(id, fly) {
  if (id != null && !markers.has(id)) { toast("존재하지 않는 센서입니다"); return false; }
  selId = id; renderUI(); const s = sensors.find(q => q.key === id); emit("sensor-select", { id, sensor: s ? { ...s } : null }); return fly ? flyTo(id) : true;
}

/* ---------- 1인칭 이동 / 충돌 ---------- */
const P = { x: 1.2, z: 3.5, yaw: -Math.PI / 2, pitch: -0.04 }, vel = { x: 0, z: 0 }, keys = new Set(); let speed = 2.2, fly = null, locked = false, flightQueue = [];
const blocked = (x, z) => x < 0.45 || x > cfg.length - 0.45 || z < RAD + 0.05 || z > cfg.width - RAD - 0.05 || rects.some(r => x > r[0] && x < r[2] && z > r[1] && z < r[3]);
function resetView() {Object.assign(P,{x:1.2,z:cfg.width/2,yaw:-Math.PI/2,pitch:-.04});fly=null;flightQueue=[];vel.x=vel.z=0;}
function startFly(to, dur) { fly = { t0: performance.now(), dur: dur * 1000, from: { ...P }, to }; }
function staticBlocked(x, z) { return x < 0.45 || x > cfg.length - 0.45 || z < RAD + 0.05 || z > cfg.width - RAD - 0.05 || rects.some(r => x > r[0] && x < r[2] && z > r[1] && z < r[3]); }
const collisionWorld = () => ({length:cfg.length,width:cfg.width,rects});
function pathClear(a,b){return clearSegment(a,b,collisionWorld());}
function findStand(t) {
  for(const distance of [2.2,2.8,3.4,4,4.6]) for(const sign of [-1,1]) {
    const x=t.x+sign*distance,z=cfg.width/2;
    if(staticBlocked(x,z))continue;
    const route=planRoute(P,{x,z},collisionWorld());if(!route)continue;
    const dx=t.x-x,dz=t.z-z,pitch=Math.atan2(t.y-EYE,Math.hypot(dx,dz));
    if(Math.abs(pitch)<=1)return {x,z,yaw:Math.atan2(-dx,-dz),pitch,route};
  }
  return null;
}
function nextFlightLeg(){const to=flightQueue.shift();if(!to){fly=null;return;}startFly(to,Math.max(.18,Math.hypot(to.x-P.x,to.z-P.z)/2.2));}
function flyTo(id){const s=sensors.find(q=>q.key===id);if(!s)return false;const target=findStand(toThree(s.x,s.y,s.z));if(!target){toast("안전한 이동 경로가 없어 이동을 취소했습니다");return false;}flightQueue=target.route.map(point=>({...point,yaw:target.yaw,pitch:target.pitch}));nextFlightLeg();return true;}
const angDiff = (a, b) => Math.atan2(Math.sin(b - a), Math.cos(b - a));
function step(dt) {
  if (fly) {
    const k = clamp((performance.now() - fly.t0) / fly.dur, 0, 1), e = k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2;
    const nx=fly.from.x+(fly.to.x-fly.from.x)*e,nz=fly.from.z+(fly.to.z-fly.from.z)*e;
    if(pointBlocked(nx,nz,collisionWorld())){fly=null;flightQueue=[];toast("이동 경로에 장애물이 있어 멈췄습니다");return;}
    P.x=nx;P.z=nz;
    P.yaw = fly.from.yaw + angDiff(fly.from.yaw, fly.to.yaw) * e; P.pitch = fly.from.pitch + (fly.to.pitch - fly.from.pitch) * e;
    if(k>=1)nextFlightLeg();if(!keys.size)return;
  }
  let f = (keys.has("KeyW") || keys.has("ArrowUp") ? 1 : 0) - (keys.has("KeyS") || keys.has("ArrowDown") ? 1 : 0), r = (keys.has("KeyD") || keys.has("ArrowRight") ? 1 : 0) - (keys.has("KeyA") || keys.has("ArrowLeft") ? 1 : 0);
  if (f || r) { fly = null; flightQueue=[]; const l = Math.hypot(f, r); f /= l; r /= l; }
  const sp = speed * (keys.has("ShiftLeft") || keys.has("ShiftRight") ? 1.8 : 1), fx = -Math.sin(P.yaw), fz = -Math.cos(P.yaw), rx = Math.cos(P.yaw), rz = -Math.sin(P.yaw);
  const k = 1 - Math.exp(-10 * dt); vel.x += ((fx * f + rx * r) * sp - vel.x) * k; vel.z += ((fz * f + rz * r) * sp - vel.z) * k;
  const nx = P.x + vel.x * dt, nz = P.z + vel.z * dt;
  if (!blocked(nx, P.z)) P.x = nx; else vel.x = 0; if (!blocked(P.x, nz)) P.z = nz; else vel.z = 0;
}

/* ---------- 입력 ---------- */
const offs = []; const on = (t, e, f, o) => { t.addEventListener(e, f, o); offs.push(() => t.removeEventListener(e, f, o)); };
const toast = (t) => { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(toast.h); toast.h = setTimeout(() => el.classList.remove("on"), 1100); };
const MOVE = ["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"];
on(window, "keydown", e => { if(e.code==='Escape' && document.pointerLockElement===cv){document.exitPointerLock();return;}if(e.target.closest?.("input,select,textarea,[contenteditable=true]") || (!locked && document.activeElement!==cv && !root.contains(document.activeElement)) || e.ctrlKey || e.metaKey || e.altKey)return; if (e.code === "KeyR") { resetView(true); return; } if (MOVE.includes(e.code) || e.code.startsWith("Shift")) { keys.add(e.code);if(MOVE.includes(e.code)){fly=null;flightQueue=[];} if (locked || document.activeElement === cv) e.preventDefault(); } });
on(window, "keyup", e => keys.delete(e.code)); on(window, "blur", () => { keys.clear(); vel.x = vel.z = 0; });
on(document, "pointerlockchange", () => { locked = document.pointerLockElement === cv; stage.classList.toggle("lock", locked); if (!locked) { keys.clear(); vel.x = vel.z = 0; } });
on(document, "visibilitychange", () => { if (document.hidden) keys.clear(); });
const look = (dx, dy) => { P.yaw -= dx * 0.0022; P.pitch = clamp(P.pitch - dy * 0.0022, -1.4, 1.4); fly = null; };
let drag = null;
on(cv, "pointerdown", e => { drag = { x: e.clientX, y: e.clientY, mv: 0 }; cv.setPointerCapture(e.pointerId); cv.focus(); });
on(cv, "pointermove", e => { if (locked) { look(e.movementX, e.movementY); return; } if (drag) { drag.mv += Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y); look((e.clientX - drag.x) * 1.6, (e.clientY - drag.y) * 1.6); drag.x = e.clientX; drag.y = e.clientY; } });
const ray = new T.Raycaster();
function pick(e) { const r = cv.getBoundingClientRect(); const v = locked || !e ? new T.Vector2(0, 0) : new T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(v, cam); const h = ray.intersectObjects([...markers.values()].map(o => o.halo), false)[0]; return h ? h.object.userData.id : null; }
on(cv, "pointerup", e => { const moved = drag && drag.mv > 5; drag = null; if (moved) return; const id = pick(e); if (id) { select(id, false); return; } if (!locked && cv.requestPointerLock) { try { const p = cv.requestPointerLock(); if (p && p.catch) p.catch(() => {}); } catch (_) {} } });
on(cv, "wheel", e => { e.preventDefault(); speed = clamp(speed - Math.sign(e.deltaY) * 0.3, 0.8, 5); $("#spd").textContent = speed.toFixed(1); toast(`이동 속도 ${speed.toFixed(1)} m/s`); }, { passive: false });
on($("#list"), "click", e => { const b = e.target.closest("[data-id]"); if (b) select(b.dataset.id, true); });
on($("#detail"), "click", e => { const b = e.target.closest("[data-go]"); if (b) flyTo(b.dataset.go); });
on($("#reset"), "click", () => resetView(true));
async function toggleFullscreen() {
  try {
    if (document.fullscreenElement === stage) await document.exitFullscreen();
    else if (stage.requestFullscreen) await stage.requestFullscreen();
    else toast("전체화면을 사용할 수 없습니다");
  } catch (_) { toast("전체화면을 사용할 수 없습니다"); }
}
function resizeViewport() {
  const w = stage.clientWidth, h = stage.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix();
}
on($("#fs"), "click", toggleFullscreen);
on($("#exit-fullscreen"), "click", toggleFullscreen);
on(document, "fullscreenchange", () => {
  const immersive = document.fullscreenElement === stage;
  $("#fs").textContent = immersive ? "전체화면 종료" : "전체화면";
  $("#fs").setAttribute("aria-pressed", String(immersive));
  keys.clear(); vel.x = vel.z = 0; drag = null;
  if (!immersive && document.pointerLockElement === cv) document.exitPointerLock();
  resizeViewport(); cv.focus({preventScroll:true});
});
const ro = new ResizeObserver(resizeViewport); ro.observe(stage);

/* ---------- 루프 ---------- */
const clock = new T.Clock(), tv = new T.Vector3(); let raf = 0, dead = false, inViewport=true, lastFrame=0;
function frame(now=performance.now()) {
  if(dead || document.hidden || !inViewport){raf=0;return;}raf=requestAnimationFrame(frame);if(now-lastFrame<1000/30)return;lastFrame=now;try { const dt = Math.min(clock.getDelta(), 0.05), t = clock.elapsedTime; step(dt);
  npcs.forEach(n => stepNpc(n, dt));
  cam.position.set(P.x, EYE, P.z); cam.rotation.set(P.pitch, P.yaw, 0);cam.updateMatrixWorld(true);
  const w = stage.clientWidth, h = stage.clientHeight;
  const occupied = [];
  markers.forEach((o, id) => {
    const d = cam.position.distanceTo(o.g.position), s = clamp(d / 6, 0.8, 2.5) * (id === selId ? 1 + 0.12 * Math.sin(t * 5) : 1);
    o.core.scale.setScalar(s); o.halo.scale.setScalar(s * (id === selId ? 2.4 : 1.6)); o.ring.scale.setScalar(s * (id === selId ? 1.3 : 1));
    o.near = isSensorNear(d, o.near);
    tv.copy(o.g.position); tv.project(cam);
    const vis = o.near && tv.z < 1 && tv.z > -1 && Math.abs(tv.x) <= 1 && Math.abs(tv.y) <= 1;
    o.lb.dataset.near = String(o.near); o.lb.setAttribute('aria-hidden', String(!vis));
    o.lb.style.opacity = vis ? 1 : 0;
    if (vis) {
      const box = labelPosition({x:(tv.x*.5+.5)*w,y:(-tv.y*.5+.5)*h}, {width:o.lb.offsetWidth,height:o.lb.offsetHeight}, {width:w,height:h}, occupied);
      occupied.push(box); o.lb.style.transform = `translate(${box.x}px,${box.y}px)`;
    }
    o.lb.classList.toggle("sel", id === selId);
  });
  renderer.render(scene, cam);
  } catch (e) { console.error("[GSOSim] frame error", e);destroy();const message=$("#fps-load-status");if(message){message.textContent="3D 표시 중 오류가 발생했습니다. 새로고침해 주세요.";message.hidden=false;} }
}

/* ---------- 외부 인터페이스 (Django 통합용) ---------- */
function setGreenhouseConfig(c) {
  const n = { name: c && c.name != null ? String(c.name).slice(0, 40) : "", length: num(c && c.length), width: num(c && c.width), height: num(c && c.height) };
  if (![n.length, n.width, n.height].every(v => Number.isFinite(v) && v >= 3)) { console.error("[GSOSim] 유효하지 않은 온실 규격", c); return false; }
  cfg = n; build(); setSensors(rawSensors); resetView(false); return true;
}
function destroy() {
  clearTimeout(toast.h);if(document.pointerLockElement===cv)document.exitPointerLock();if(document.fullscreenElement===stage)document.exitFullscreen().catch(()=>{});visibilityObserver.disconnect();
  if (dead) return; dead = true; keys.clear();vel.x=vel.z=0;fly=null;flightQueue=[];locked=false;drag=null;stage.classList.remove("lock");cancelAnimationFrame(raf); offs.forEach(f => f()); ro.disconnect(); markers.forEach(o => o.lb.remove()); markers.clear();sensors=[];rawSensors=[];staticSensors=[];lastRecords=null; disposeTree(world); Object.values(GEO).forEach(g => g.dispose()); Object.values(MAT).flatMap(materials=>Object.values(materials)).forEach(m => m.dispose());sun.shadow.map?.dispose();sun.shadow.mapPass?.dispose();scene.clear(); renderer.dispose();emit('destroy',null); if (window.GSOSim === api) window.GSOSim = null;
}
const safe = (fn, fb) => (...a) => { if(dead)return fb;try { return fn(...a); } catch (e) { console.error("[GSOSim]", e); return fb; } };
function applyRecords() { if (!lastRecords) return null; const res = fromRecords(lastRecords, { at: lastAt }); adapterIssues = res.issues; histTimes = res.times; histories = res.histories; setSensors(res.sensors.concat(staticSensors)); return res; }
const api = {
  version: "1.1",
  setGreenhouseConfig: safe(c => { if(![c?.length,c?.width,c?.height].map(num).every(v=>Number.isFinite(v)&&v>=3))return false;if (isDemo) { isDemo = false; rawSensors = []; } return setGreenhouseConfig(c); }, false),
  setSensors: safe(l => { isDemo = false; lastRecords = null; staticSensors=[]; adapterIssues = []; histTimes = []; histories = {}; setSensors(l); return true; }, false),
  setRecords: safe((r, o) => { isDemo = false; staticSensors=Array.isArray(o?.staticSensors)?o.staticSensors:[]; lastRecords = Array.isArray(r) ? r : []; lastAt = o && o.at != null ? String(o.at) : ""; return applyRecords(); }, null),
  setTime: safe(at => { lastAt = at == null ? "" : String(at); return applyRecords(); }, null),
  init: safe(o => { o = o || {};if(o.config && ![o.config.length,o.config.width,o.config.height].map(num).every(v=>Number.isFinite(v)&&v>=3))return false; isDemo = false; rawSensors = []; lastRecords = null; adapterIssues = []; histTimes = []; histories = {}; if(o.config && !setGreenhouseConfig(o.config))return false;staticSensors=Array.isArray(o.sensors)?o.sensors:[]; if (o.records) { lastRecords = o.records; lastAt = o.at != null ? String(o.at) : ""; applyRecords(); } else setSensors(o.sensors || []);isDemo=!!o.demo;renderUI(); resetView(false); return true; }, false),
  fromRecords, roofAt, focusSensor: safe((id,type="measured",fly=true) => select(sensorKey({id,positionType:type}),fly),false), resetView: () => resetView(true), toThree, destroy,
  getSensors: () => sensors.map(s => ({ ...s })), getHistories: () => JSON.parse(JSON.stringify(histories)), getIssues: () => ({ rejected: rejected.map(r => ({ ...r })), adapter: adapterIssues.slice() }), isDemo: () => isDemo
  ,getState: () => ({config:{...cfg},player:{...P},speed,autoMoving:!!fly,at:lastAt,selectedType:sensors.find(s=>s.key===selId)?.positionType || null,markerStyles:[...markers.values()].map(o=>({positionType:sensors.find(s=>markers.get(s.key)===o)?.positionType,isRecommended:sensors.find(s=>markers.get(s.key)===o)?.isRecommended===true,core:o.core.material.color.getHexString(),halo:o.halo.material.color.getHexString(),ring:o.ring.material.color.getHexString(),leader:o.leader.material.color.getHexString(),foot:o.foot.material.color.getHexString()})),selected:sensors.find(s=>s.key===selId)?.id || null,npcs:npcs.map(n=>({x:n.x,z:n.z})),beds:rects.map(r=>r.slice()),dead,memory:{...renderer.info.memory}})
};
window.GSOSim = api;

function resume(){if(dead)return;if(document.hidden||!inViewport){cancelAnimationFrame(raf);raf=0;keys.clear();fly=null;flightQueue=[];}else if(!raf){clock.getDelta();raf=requestAnimationFrame(frame);}}
const visibilityObserver=new IntersectionObserver(entries=>{inViewport=entries[0].isIntersecting;resume();});visibilityObserver.observe(stage);
on(document,"visibilitychange",resume);
on(window,"pagehide",event=>{if(event.persisted){cancelAnimationFrame(raf);raf=0;}else destroy();});on(window,"pageshow",resume);
if(!api.init(initial))throw new Error("시뮬레이터 초기화에 실패했습니다.");
isDemo=!!initial.demo;renderUI();resetView();frame();

return api;
}
