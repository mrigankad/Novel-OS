import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./fonts/sf-pro.css";
// Mono reader option + legacy code surfaces
import "@fontsource-variable/google-sans-code/index.css";
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/400-italic.css";

import "./theme";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
