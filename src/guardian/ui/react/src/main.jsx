import {createRoot} from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";
import "./dev/liveReload.js";

createRoot(document.getElementById("root")).render(<App/>);
