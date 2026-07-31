import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted variable fonts (no render-blocking CDN @import, no FOUT).
// Google Sans Flex/Code are OFL-licensed; "Google Sans" proper is Google-restricted.
import "@fontsource-variable/google-sans-flex/index.css";
import "@fontsource-variable/google-sans-code/index.css";
// Newsreader is no longer a default. It stays as a reader font option
// on the manuscript canvas (see ReaderFont in theme.ts).
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
