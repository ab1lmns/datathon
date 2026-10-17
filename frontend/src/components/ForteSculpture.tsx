import { useEffect, useRef, useState } from 'react';
import logoSvg from '../assets/forte-logo.svg?raw';
import logoUrl from '../assets/forte-logo.svg';
import { BRAND_TURN_MS, BRAND_SETTLE_MS, BRAND_FLIGHT_MS } from './brandMotion';

/** The original wordmark, extruded locally and lit like a small enamel sign. */
export function ForteSculpture({ onActivate, intro = false, onReady }: { onActivate?: () => void; intro?: boolean; onReady?: () => void }) {
  const host = useRef<HTMLButtonElement>(null);
  const pointer = useRef({ x: 0, y: 0 });
  const [ready, setReady] = useState(false);
  const readyCallback = useRef(onReady);
  readyCallback.current = onReady;

  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};

    async function mount() {
      const [THREE, { SVGLoader }, { RoomEnvironment }] = await Promise.all([
        import('three'),
        import('three/addons/loaders/SVGLoader.js'),
        import('three/addons/environments/RoomEnvironment.js'),
      ]);
      if (disposed || !host.current) return;
      const element = host.current;
      let renderer: InstanceType<typeof THREE.WebGLRenderer>;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
      } catch { readyCallback.current?.(); return; } // Keep the SVG fallback without WebGL2.
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setClearColor(0x000000, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.1;
      renderer.domElement.setAttribute('aria-hidden', 'true');
      element.appendChild(renderer.domElement);

      const scene = new THREE.Scene();
      // Orthographic projection keeps every letter the same size.
      const camera = new THREE.OrthographicCamera(-3.5, 3.5, 1.5, -1.5, 0.1, 30);
      camera.position.set(0, 0, 8);
      const studio = new RoomEnvironment();
      const generator = new THREE.PMREMGenerator(renderer);
      const environment = generator.fromScene(studio, 0.04);
      scene.environment = environment.texture;
      scene.environmentIntensity = 0.75;
      studio.dispose();
      generator.dispose();

      const key = new THREE.DirectionalLight(0xfff4f6, 2.6);
      key.position.set(-3, 5, 7);
      const fill = new THREE.DirectionalLight(0xffffff, 0.8);
      fill.position.set(4, 1, 5);
      scene.add(key, fill);

      const face = new THREE.MeshPhysicalMaterial({
        color: intro ? 0xfff8fb : 0x9f1246, metalness: 0.2, roughness: 0.3,
        clearcoat: 0.8, clearcoatRoughness: 0.22,
      });
      const edge = new THREE.MeshStandardMaterial({
        color: intro ? 0xc985a3 : 0x710d34, metalness: 0.3, roughness: 0.28,
      });
      const introFace = new THREE.Color(0xfff8fb), finalFace = new THREE.Color(0x9f1246);
      const introEdge = new THREE.Color(0xc985a3), finalEdge = new THREE.Color(0x710d34);
      const geometries: InstanceType<typeof THREE.ExtrudeGeometry>[] = [];
      const wordmark = new THREE.Group();
      new SVGLoader().parse(logoSvg).paths.forEach(path => {
        path.toShapes().forEach(shape => {
          const geometry = new THREE.ExtrudeGeometry(shape, {
            depth: 8, bevelEnabled: true, bevelSegments: 4,
            steps: 1, bevelSize: 0.32, bevelThickness: 0.4, curveSegments: 16,
          });
          geometry.translate(-50.5, -15, -4);
          geometries.push(geometry);
          wordmark.add(new THREE.Mesh(geometry, [face, edge]));
        });
      });
      wordmark.scale.set(0.06, -0.06, 0.06);
      // YXZ preserves a level baseline while revealing the top and side faces.
      wordmark.rotation.set(0.18, -0.28, 0, 'YXZ');
      scene.add(wordmark);

      let frame = 0, inView = true, last = 0;
      let firstFrame: number | null = null;
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
      function render(time = 0) {
        if (disposed) return;
        if (intro || time - last >= 32 || reduced.matches) {
          const t = time / 1000;
          const elapsed = Math.min(Math.max(time - last, 0), 64);
          const ease = reduced.matches ? 1 : 1 - Math.exp(-elapsed / 160);
          const x = reduced.matches ? 0 : pointer.current.x * 0.3;
          const y = reduced.matches ? 0 : pointer.current.y * 0.16;
          const breathe = reduced.matches ? 0 : Math.sin(t * 0.85) * 0.12;
          if (intro && !reduced.matches) {
            const progress = Math.min(Math.max((time - (firstFrame ?? time)) / BRAND_TURN_MS, 0), 1);
            // Quintic easing gives zero velocity and acceleration at both ends.
            const turn = progress ** 3 * (progress * (progress * 6 - 15) + 10);
            wordmark.rotation.y = -0.28 + Math.PI * 2 * (1 - turn);
            wordmark.rotation.x = 0.18;
            const tint = Math.min(Math.max((time - (firstFrame ?? time) - BRAND_TURN_MS - BRAND_SETTLE_MS) / BRAND_FLIGHT_MS, 0), 1);
            face.color.lerpColors(introFace, finalFace, tint);
            edge.color.lerpColors(introEdge, finalEdge, tint);
          } else {
            wordmark.rotation.y += (-0.28 + x + breathe - wordmark.rotation.y) * ease;
            wordmark.rotation.x += (0.18 + y + (reduced.matches ? 0 : Math.sin(t * 0.65) * 0.045) - wordmark.rotation.x) * ease;
          }
          renderer.render(scene, camera);
          if (firstFrame === null) { firstFrame = time; setReady(true); readyCallback.current?.(); }
          last = time;
        }
        if (!reduced.matches && inView && !document.hidden) frame = requestAnimationFrame(render);
      }
      function start() {
        cancelAnimationFrame(frame);
        if (inView && !document.hidden) frame = requestAnimationFrame(render);
      }
      const resize = new ResizeObserver(() => {
        const { clientWidth: width, clientHeight: height } = element;
        if (!width || !height) return;
        renderer.setSize(width, height);
        const aspect = width / height;
        const halfHeight = Math.max(1.4, 3.4 / aspect);
        camera.left = -halfHeight * aspect;
        camera.right = halfHeight * aspect;
        camera.top = halfHeight;
        camera.bottom = -halfHeight;
        camera.updateProjectionMatrix();
        start();
      });
      resize.observe(element);
      const observer = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; start(); });
      observer.observe(element);
      document.addEventListener('visibilitychange', start);
      reduced.addEventListener('change', start);
      start();

      cleanup = () => {
        cancelAnimationFrame(frame);
        resize.disconnect();
        observer.disconnect();
        document.removeEventListener('visibilitychange', start);
        reduced.removeEventListener('change', start);
        geometries.forEach(geometry => geometry.dispose());
        face.dispose();
        edge.dispose();
        environment.dispose();
        renderer.dispose();
        renderer.domElement.remove();
      };
    }
    mount().catch(() => { if (!disposed) readyCallback.current?.(); });
    return () => { disposed = true; cleanup(); };
  }, [intro]);

  return <button
    ref={host}
    className={`forte-sculpture ${intro ? 'startup-sculpture' : 'header-sculpture'} ${ready ? 'is-ready' : ''}`}
    aria-label={intro ? undefined : 'Forte — обзор'}
    aria-hidden={intro || undefined}
    tabIndex={intro ? -1 : undefined}
    title={intro ? undefined : 'Forte — обзор'}
    onPointerMove={event => {
      if (event.pointerType !== 'mouse') return;
      const bounds = event.currentTarget.getBoundingClientRect();
      pointer.current = { x: (event.clientX - bounds.left) / bounds.width - 0.5, y: (event.clientY - bounds.top) / bounds.height - 0.5 };
    }}
    onPointerLeave={() => { pointer.current = { x: 0, y: 0 }; }}
    onClick={onActivate}
  ><img src={logoUrl} alt="" className="sculpture-fallback"/><span className="sculpture-shadow" aria-hidden="true"/></button>;
}
