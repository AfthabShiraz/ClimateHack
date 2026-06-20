import { useEffect, useRef } from "react";
import * as Cesium from "cesium";
import {
  useStore, BAND_COLOR, exposureAt, rpiFromExposure, bandForRpi,
  type Hospital, type LngLat,
} from "../state/store";

const ION_TOKEN = import.meta.env.VITE_CESIUM_ION_TOKEN as string | undefined;
const GOOGLE_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined;

// world-anchored plume dome (metres) — geographic, so it never scales wrong with zoom
const PLUME_RADIUS_M = 2600;
const PLUME_HEIGHT_M = 1300;
const COLUMN_BASE_HEIGHT = 40;
const RPI_TO_METRES = 22;
const RING_RADIUS = 550;
const BEACON_RADIUS = 700;
const DRIFT_MS = 3800;
const HORIZON_SCALE: Record<string, number> = { now: 1, "3d": 1.18, "7d": 1.4 };

const easeInOut = (t: number) => (t < 0.5 ? 4 * t ** 3 : 1 - Math.pow(-2 * t + 2, 3) / 2);
const lerpLL = (a: LngLat, b: LngLat, t: number): LngLat => ({
  lon: a.lon + (b.lon - a.lon) * t,
  lat: a.lat + (b.lat - a.lat) * t,
});

export default function CesiumMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);

  const heights = useRef<Record<string, number>>({});
  const colors = useRef<Record<string, Cesium.Color>>({});
  const shows = useRef({ columns: true });
  const selected = useRef<string | null>(null);
  const alertSet = useRef<Set<string>>(new Set());

  // plume drift state (refs → smooth 60fps, no React re-render)
  const plumeCenter = useRef<LngLat | null>(null);
  const driftTo = useRef<LngLat | null>(null);
  const driftFrom = useRef<LngLat | null>(null);
  const driftStart = useRef<number>(0);
  const driftActive = useRef<boolean>(false);

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;
    if (ION_TOKEN) Cesium.Ion.defaultAccessToken = ION_TOKEN;

    const viewer = new Cesium.Viewer(containerRef.current, {
      baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
      navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
      infoBox: false, selectionIndicator: false,
      baseLayer: false as unknown as Cesium.ImageryLayer,
    });
    viewerRef.current = viewer;

    viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#06080f");
    viewer.clock.shouldAnimate = true;
    viewer.scene.globe.show = false;
    if (viewer.scene.skyBox) viewer.scene.skyBox.show = false;
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = false;
    viewer.scene.fog.enabled = false;

    const homeView = () =>
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(-0.115, 51.42, 6500),
        orientation: { heading: 0, pitch: Cesium.Math.toRadians(-32), roll: 0 },
      });
    homeView();

    (async () => {
      try {
        if (GOOGLE_KEY) {
          viewer.scene.primitives.add(await Cesium.createGooglePhotorealistic3DTileset({ key: GOOGLE_KEY }));
        } else if (ION_TOKEN) {
          viewer.scene.globe.show = true;
          viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1020");
          viewer.scene.primitives.add(await Cesium.createOsmBuildingsAsync());
        } else {
          viewer.scene.globe.show = true;
          viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1020");
        }
      } catch (e) {
        console.warn("[Crosssight] base tiles failed", e);
        viewer.scene.globe.show = true;
        viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1020");
      }
      homeView();
    })();

    const list = useStore.getState().hospitals;
    for (const h of list) {
      heights.current[h.id] = h.rpi * RPI_TO_METRES;
      colors.current[h.id] = Cesium.Color.fromCssColorString(BAND_COLOR[h.band]).withAlpha(0.82);
      const isSel = () => selected.current === h.id;
      const isAlert = () => alertSet.current.has(h.id);

      // column
      viewer.entities.add({
        id: h.id,
        name: h.name,
        position: new Cesium.CallbackProperty(
          () => Cesium.Cartesian3.fromDegrees(h.lon, h.lat, COLUMN_BASE_HEIGHT + (heights.current[h.id] ?? 0) / 2),
          false
        ) as unknown as Cesium.PositionProperty,
        cylinder: {
          length: new Cesium.CallbackProperty(() => heights.current[h.id] ?? 0, false),
          topRadius: 300, bottomRadius: 300,
          material: new Cesium.ColorMaterialProperty(
            new Cesium.CallbackProperty(() => colors.current[h.id], false)
          ),
          outline: true, outlineColor: Cesium.Color.WHITE.withAlpha(0.25),
          show: new Cesium.CallbackProperty(() => shows.current.columns && !isSel(), false),
        },
      });

      // selection ring (draped) + floating halo
      viewer.entities.add({
        id: `${h.id}__ring`,
        position: Cesium.Cartesian3.fromDegrees(h.lon, h.lat, 0),
        ellipse: {
          semiMajorAxis: RING_RADIUS, semiMinorAxis: RING_RADIUS,
          material: new Cesium.ColorMaterialProperty(
            new Cesium.CallbackProperty(() => (colors.current[h.id] ?? Cesium.Color.CYAN).withAlpha(0.4), false)
          ),
          classificationType: Cesium.ClassificationType.CESIUM_3D_TILE,
          show: new Cesium.CallbackProperty(() => isSel(), false),
        },
      });
      viewer.entities.add({
        id: `${h.id}__halo`,
        position: Cesium.Cartesian3.fromDegrees(h.lon, h.lat, 350),
        ellipse: {
          semiMajorAxis: RING_RADIUS, semiMinorAxis: RING_RADIUS, height: 350,
          fill: false, outline: true, outlineWidth: 5,
          outlineColor: new Cesium.CallbackProperty(() => (colors.current[h.id] ?? Cesium.Color.CYAN).withAlpha(0.95), false),
          show: new Cesium.CallbackProperty(() => isSel(), false),
        },
      });

      // alert beacon — pulsing red ground glow on flagged (red) hospitals
      viewer.entities.add({
        id: `${h.id}__beacon`,
        position: Cesium.Cartesian3.fromDegrees(h.lon, h.lat, 0),
        ellipse: {
          semiMajorAxis: BEACON_RADIUS, semiMinorAxis: BEACON_RADIUS,
          material: new Cesium.ColorMaterialProperty(
            new Cesium.CallbackProperty(() => {
              const ph = (Date.now() % 1600) / 1600;
              return Cesium.Color.fromCssColorString("#e71d36").withAlpha(0.32 * (1 - ph));
            }, false)
          ),
          classificationType: Cesium.ClassificationType.CESIUM_3D_TILE,
          show: new Cesium.CallbackProperty(() => isAlert() && !isSel(), false),
        },
      });
    }

    // click to select
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((click: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      const picked = viewer.scene.pick(click.position);
      if (Cesium.defined(picked) && picked.id?.id) {
        useStore.getState().select(String(picked.id.id).replace(/__(ring|halo|beacon)$/, ""));
      } else {
        useStore.getState().select(null);
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // ---- world-anchored plume dome (a translucent sphere of pollution) ----
    viewer.entities.add({
      id: "__plume",
      position: new Cesium.CallbackProperty(() => {
        const c = plumeCenter.current;
        return c
          ? Cesium.Cartesian3.fromDegrees(c.lon, c.lat, PLUME_HEIGHT_M)
          : undefined;
      }, false) as unknown as Cesium.PositionProperty,
      ellipsoid: {
        radii: new Cesium.Cartesian3(PLUME_RADIUS_M, PLUME_RADIUS_M, PLUME_HEIGHT_M),
        material: new Cesium.ColorMaterialProperty(
          new Cesium.CallbackProperty(() => {
            const ph = (Date.now() % 3200) / 3200;
            const a = 0.14 + 0.05 * Math.sin(ph * Math.PI * 2); // gentle breathing
            return Cesium.Color.fromCssColorString("#e71d36").withAlpha(a);
          }, false)
        ),
        outline: true,
        outlineColor: Cesium.Color.fromCssColorString("#ff8c42").withAlpha(0.5),
        show: new Cesium.CallbackProperty(
          () => !!plumeCenter.current && useStore.getState().layers.exposure,
          false
        ),
      },
    });

    // ---- the per-frame engine: plume drift + live exposure → columns/haze/beacons ----
    const onFrame = () => {
      const s = useStore.getState();
      selected.current = s.selectedId;
      shows.current.columns = s.layers.columns;

      // resolve plume centre (with smooth drift)
      const target = s.simActive ? s.plumeTarget : null;
      if (!target) {
        plumeCenter.current = null;
        driftActive.current = false;
        driftTo.current = null;
      } else if (s.drifting) {
        const changed =
          !driftTo.current || driftTo.current.lon !== target.lon || driftTo.current.lat !== target.lat;
        if (changed) {
          driftFrom.current = plumeCenter.current ?? target;
          driftTo.current = target;
          driftStart.current = performance.now();
          driftActive.current = true;
        }
        if (driftActive.current) {
          const t = Math.min(1, (performance.now() - driftStart.current) / DRIFT_MS);
          plumeCenter.current = lerpLL(driftFrom.current!, driftTo.current!, easeInOut(t));
          if (t >= 1) {
            driftActive.current = false;
            useStore.getState().arrive();
          }
        }
      } else {
        plumeCenter.current = target; // snap (first epicentre / settled)
        driftTo.current = target;
        driftActive.current = false;
      }

      // compute live exposure → columns + alerts
      const scale = HORIZON_SCALE[s.horizon] ?? 1;
      const nextAlerts = new Set<string>();
      for (const h of s.hospitals) {
        const e = exposureAt(h, plumeCenter.current);
        const rpi = Math.min(100, rpiFromExposure(e, h.vulnerabilityWeight, h.roadside) * scale);
        heights.current[h.id] = rpi * RPI_TO_METRES;
        const c = Cesium.Color.fromCssColorString(BAND_COLOR[bandForRpi(rpi)]);
        colors.current[h.id] = c.withAlpha(s.selectedId === h.id ? 1 : 0.82);
        if (rpi >= 70) nextAlerts.add(h.id);
      }
      alertSet.current = nextAlerts;
    };
    viewer.scene.preRender.addEventListener(onFrame);

    return () => {
      viewer.scene.preRender.removeEventListener(onFrame);
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // fly to a freshly-selected hospital
  useEffect(() => {
    return useStore.subscribe((s, prev) => {
      if (s.selectedId && s.selectedId !== prev.selectedId && viewerRef.current) {
        const h = s.hospitals.find((x: Hospital) => x.id === s.selectedId);
        if (h) {
          viewerRef.current.camera.flyToBoundingSphere(
            new Cesium.BoundingSphere(Cesium.Cartesian3.fromDegrees(h.lon, h.lat, COLUMN_BASE_HEIGHT), RING_RADIUS),
            { offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-35), 2600), duration: 1.2 }
          );
        }
      }
    });
  }, []);

  return <div ref={containerRef} className="cesium-root" />;
}
