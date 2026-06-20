/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CESIUM_ION_TOKEN?: string;
  readonly VITE_GOOGLE_MAPS_KEY?: string;
  readonly VITE_BACKEND_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
