import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@fontsource-variable/inter-tight/index.css";
import "@fontsource/urbanist/700.css";
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/600.css";
import "@fontsource/newsreader/400-italic.css";

import "./theme";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
