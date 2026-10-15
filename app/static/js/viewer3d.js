/*
 * A 3D viewer for plant scans and models: STL, PLY (meshes and point clouds),
 * OBJ and glTF/GLB. Drag to turn, scroll to zoom, right-drag to move.
 * Uses three.js (MIT), kept in this repository under static/vendor.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const PLANT = 0x4d9f4a;

function meshOf(geometry) {
  if (!geometry.attributes.normal) geometry.computeVertexNormals();
  const coloured = !!geometry.attributes.color;
  return new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
    color: coloured ? 0xffffff : PLANT, vertexColors: coloured, roughness: 0.8, metalness: 0, side: THREE.DoubleSide,
  }));
}

async function load(buffer, filename) {
  const ext = filename.split('.').pop().toLowerCase();
  if (ext === 'stl') return meshOf(new STLLoader().parse(buffer));
  if (ext === 'ply') {
    const geometry = new PLYLoader().parse(buffer);
    if (geometry.index) return meshOf(geometry);
    // Without faces it is a point cloud, as scanners often save.
    const coloured = !!geometry.attributes.color;
    const box = new THREE.Box3().setFromBufferAttribute(geometry.attributes.position);
    const size = box.getSize(new THREE.Vector3()).length() || 1;
    return new THREE.Points(geometry, new THREE.PointsMaterial({
      size: size / 400, vertexColors: coloured, color: coloured ? 0xffffff : PLANT }));
  }
  if (ext === 'obj') {
    const group = new OBJLoader().parse(new TextDecoder().decode(buffer));
    group.traverse((o) => { if (o.isMesh && !o.material.map) o.material = new THREE.MeshStandardMaterial({ color: PLANT, side: THREE.DoubleSide }); });
    return group;
  }
  if (ext === 'glb' || ext === 'gltf') {
    const gltf = await new Promise((resolve, reject) => new GLTFLoader().parse(buffer, '', resolve, reject));
    return gltf.scene;
  }
  throw new Error(`.${ext} files cannot be shown; download it instead`);
}

/** Show a model, fetched from `url`, in `holder`, until the holder leaves the page. */
export async function show(holder, url, filename) {
  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`could not fetch it (${res.status})`);
  const object = await load(await res.arrayBuffer(), filename);

  const width = holder.clientWidth || 800;
  const height = Math.max(320, Math.round(window.innerHeight * 0.6));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf8fafc);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(1, 2, 1.5);
  scene.add(sun);
  scene.add(object);

  // Centre it and stand back far enough to see all of it.
  const box = new THREE.Box3().setFromObject(object);
  const centre = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length() || 1;
  object.position.sub(centre);
  const camera = new THREE.PerspectiveCamera(45, width / height, size / 1000, size * 100);
  camera.position.set(size * 0.6, size * 0.45, size * 0.9);
  sun.position.multiplyScalar(size);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(width, height);
  holder.replaceChildren(renderer.domElement);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  const tick = () => {
    if (!holder.isConnected) {          // the dialog was closed: let it all go
      renderer.dispose();
      controls.dispose();
      return;
    }
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  };
  tick();
}
