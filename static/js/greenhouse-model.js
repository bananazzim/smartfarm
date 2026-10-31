// Data (X length, Y width, Z height) -> Three (X, Y up, Z width).
export function toScene(THREE, sensor, width) {
  return new THREE.Vector3(sensor.x, sensor.z, sensor.y - width / 2);
}

// The same model framing and camera are used in DEMO and customer scenes.
export function fitHouseView(THREE, camera, length, width, height) {
  camera.zoom = 1;
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  const points = [];
  for (const x of [0,length]) for (const y of [0,height]) for (const z of [-width/2,width/2]) {
    points.push(new THREE.Vector3(x,y,z).project(camera));
  }
  const edgeX = Math.max(...points.map(p=>Math.abs(p.x)));
  const edgeY = Math.max(...points.map(p=>Math.abs(p.y)));
  camera.zoom = Math.min(.90/edgeX,.84/edgeY);
  camera.updateProjectionMatrix();
}

export function resetHouseView(THREE, camera, controls, length, width, height) {
  const size = Math.max(length,width,height);
  camera.position.set(length*1.22+size*.2,height*1.25+size*.42,width*1.45+size*.25);
  controls.target.set(length/2,height*.4,0);
  controls.update();
  fitHouseView(THREE,camera,length,width,height);
}

export function addGreenhouse(THREE, scene, length, width, height, shape = 'single') {
  const floor = new THREE.Mesh(new THREE.BoxGeometry(length, .04, width), new THREE.MeshStandardMaterial({color: 0xffffff, roughness: .9}));
  floor.position.set(length / 2, -.03, 0);
  scene.add(floor);
  if (shape !== 'single') {
    // Connected spans: only show the registered bounding volume, not invented bays.
    const geometry = new THREE.BoxGeometry(length,height,width);
    const cover = new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xb9deef,transparent:true,opacity:.14,depthWrite:false,side:THREE.DoubleSide}));
    cover.position.set(length/2,height/2,0);
    scene.add(cover);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry),new THREE.LineBasicMaterial({color:0x96acba}));
    edges.position.copy(cover.position); scene.add(edges);
    return;
  }
  const eave = height * .68;
  const material = new THREE.LineBasicMaterial({color: 0x96acba, transparent: true, opacity: .65});
  const addLine = (points) => scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material));
  const roofPoint = (x, step) => {
    const theta = Math.PI * step / 32;
    return new THREE.Vector3(x, eave + height * .32 * Math.sin(theta), -width / 2 * Math.cos(theta));
  };
  for (let rib = 0; rib < 5; rib++) {
    const x = length * rib / 4;
    const points = [new THREE.Vector3(x, 0, -width / 2)];
    for (let step = 0; step <= 32; step++) points.push(roofPoint(x, step));
    points.push(new THREE.Vector3(x, 0, width / 2));
    addLine(points);
  }
  for (const side of [-1, 1]) {
    addLine([new THREE.Vector3(0, eave, side*width/2), new THREE.Vector3(length, eave, side*width/2)]);
  }
  // One continuous transparent surface with real depth testing; markers retain their depth.
  const vertices = [];
  function quad(a,b,c,d) {
    for (const point of [a,b,c,a,c,d]) vertices.push(point.x,point.y,point.z);
  }
  for (let step=0; step<32; step++) quad(roofPoint(0,step),roofPoint(length,step),roofPoint(length,step+1),roofPoint(0,step+1));
  for (const side of [-1,1]) quad(new THREE.Vector3(0,0,side*width/2),new THREE.Vector3(length,0,side*width/2),new THREE.Vector3(length,eave,side*width/2),new THREE.Vector3(0,eave,side*width/2));
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  geometry.computeVertexNormals();
  scene.add(new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xb9deef,transparent:true,opacity:.14,side:THREE.DoubleSide,depthWrite:false,roughness:.5})));
}
