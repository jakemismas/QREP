import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AnnotatePage } from "./AnnotatePage";

// The app's theme switch is not on this page; follow the system setting.
document.documentElement.dataset.skin = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AnnotatePage />
  </StrictMode>,
);
