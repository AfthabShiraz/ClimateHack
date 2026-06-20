import * as Cesium from "cesium";
import type { Wind, Hospital } from "../state/store";

// A soft radial-gradient sprite used as the haze particle.
function glowSprite(): HTMLCanvasElement {
  const s = 64;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  // near-solid core with a crisp edge → particles read as defined spheres, not fuzzy haze
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.78, "rgba(255,255,255,0.97)");
  g.addColorStop(0.92, "rgba(255,255,255,0.6)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, s, s);
  return c;
}

// Green -> amber -> red as exposure climbs.
function exposureColor(i: number): Cesium.Color {
  const stops: [number, string][] = [
    [0, "#37d39a"],
    [0.45, "#ffd166"],
    [0.7, "#ff8c42"],
    [1, "#e71d36"],
  ];
  let a = stops[0], b = stops[stops.length - 1];
  for (let k = 0; k < stops.length - 1; k++) {
    if (i >= stops[k][0] && i <= stops[k + 1][0]) { a = stops[k]; b = stops[k + 1]; break; }
  }
  const t = (i - a[0]) / (b[0] - a[0] || 1);
  return Cesium.Color.lerp(
    Cesium.Color.fromCssColorString(a[1]),
    Cesium.Color.fromCssColorString(b[1]),
    t,
    new Cesium.Color()
  );
}

export interface HazeHandle {
  update: (exposuresById: Record<string, number>, wind: Wind, show: boolean) => void;
  destroy: () => void;
}

const SPRITE = glowSprite();

// Exposure below this shows NO haze at all (clean air = clear sky).
const HAZE_THRESHOLD = 0.4;
// Keep particles roughly world-anchored: their pixel size = WORLD_RADIUS metres
// projected at the current camera height, so zooming out shrinks them on screen
// (otherwise screen-space billboards balloon to cover the whole country).
const WORLD_RADIUS = 1500; // metres a particle should roughly span
const PROJ_K = 780; // ≈ viewportHeight / (2·tan(fov/2))

// One small drifting emitter per catchment → a spatially-varied field, not a uniform cloud.
// (Stand-in for ~100 per-station LAQN readings; real feed swaps in at M3.)
export function createHaze(viewer: Cesium.Viewer, hospitals: Hospital[]): HazeHandle {
  const wind: Wind = { dirDeg: 235, speedMs: 4 };
  const systems = new Map<string, Cesium.ParticleSystem>();

  // keep particle world-size constant by rescaling pixels with camera height
  const onPreRender = () => {
    const h = viewer.camera.positionCartographic?.height ?? 6500;
    const px = Math.max(3, Math.min(420, (WORLD_RADIUS / h) * PROJ_K));
    const size = new Cesium.Cartesian2(px, px);
    for (const sys of systems.values()) {
      sys.minimumImageSize = size;
      sys.maximumImageSize = size;
    }
  };

  for (const h of hospitals) {
    const sys = new Cesium.ParticleSystem({
      image: SPRITE,
      startColor: exposureColor(h.exposure).withAlpha(0.25),
      endColor: exposureColor(h.exposure).withAlpha(0.0),
      startScale: 0.7,
      endScale: 3.0,
      particleLife: 6.0,
      speed: 1.0,
      imageSize: new Cesium.Cartesian2(520, 520),
      emissionRate: 6,
      modelMatrix: Cesium.Transforms.eastNorthUpToFixedFrame(
        Cesium.Cartesian3.fromDegrees(h.lon, h.lat, 350)
      ),
      // a modest local cell so neighbouring catchments read as distinct
      emitter: new Cesium.BoxEmitter(new Cesium.Cartesian3(2600, 2600, 500)),
      updateCallback: (p: Cesium.Particle) => {
        const toDir = Cesium.Math.toRadians((wind.dirDeg + 180) % 360);
        const speed = wind.speedMs * 45;
        p.velocity = new Cesium.Cartesian3(Math.sin(toDir) * speed, Math.cos(toDir) * speed, 3);
      },
      lifetime: Number.MAX_VALUE,
    });
    viewer.scene.primitives.add(sys);
    systems.set(h.id, sys);
  }

  viewer.scene.preRender.addEventListener(onPreRender);

  return {
    update(exposuresById, w, show) {
      wind.dirDeg = w.dirDeg;
      wind.speedMs = w.speedMs;
      for (const [id, sys] of systems) {
        const e = exposuresById[id] ?? 0;
        // below threshold → no haze at all; above → ramp from 0
        const t = e <= HAZE_THRESHOLD ? 0 : (e - HAZE_THRESHOLD) / (1 - HAZE_THRESHOLD);
        const visible = show && t > 0;
        sys.show = visible;
        sys.emissionRate = visible ? t * 16 : 0;
        sys.startColor = exposureColor(e).withAlpha(t * 0.1); // very low opacity
        sys.endColor = exposureColor(e).withAlpha(0.0);
        sys.endScale = 1.4 + t * 0.8;
      }
    },
    destroy() {
      viewer.scene.preRender.removeEventListener(onPreRender);
      for (const sys of systems.values()) viewer.scene.primitives.remove(sys);
      systems.clear();
    },
  };
}
