import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

// NOTE: no StrictMode — it double-mounts in dev and races the Cesium viewer/camera.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
