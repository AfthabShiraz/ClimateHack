import { useEffect } from "react";
import CesiumMap from "./cesium/CesiumMap";
import TopBar from "./ui/TopBar";
import LeftRail from "./ui/LeftRail";
import RightPanel from "./ui/RightPanel";
import Drawer from "./ui/Drawer";
import { useStore } from "./state/store";

export default function App() {
  const init = useStore((s) => s.init);
  useEffect(() => {
    void init();
  }, [init]);

  return (
    <div className="app">
      <CesiumMap />
      <div className="overlay">
        <TopBar />
        <div className="mid">
          <LeftRail />
          <div className="map-spacer" />
          <RightPanel />
        </div>
      </div>
      <Drawer />
    </div>
  );
}
