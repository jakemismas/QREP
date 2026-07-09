import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import SpikePage from "./SpikePage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SpikePage />
  </StrictMode>,
);
