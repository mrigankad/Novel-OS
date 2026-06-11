import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted variable fonts (no render-blocking CDN @import, no FOUT).
import "@fontsource-variable/fraunces/index.css";
import "@fontsource-variable/fraunces/opsz-italic.css";
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/400-italic.css";
import "@fontsource-variable/hanken-grotesk/index.css";

import "./theme";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
