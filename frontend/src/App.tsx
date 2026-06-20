import CesiumMap from "./cesium/CesiumMap";
import TopBar from "./ui/TopBar";
import LeftRail from "./ui/LeftRail";
import RightPanel from "./ui/RightPanel";
import Drawer from "./ui/Drawer";

export default function App() {
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
