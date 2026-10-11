/*
 * Photo-reverse screens (S6 issue #46; S2 sprint 3 issue #68; PARITY items
 * 6, 7, 14, 17 + the sprint 3 amendment). Picks the photo-flow screen off
 * usePhoto().state:
 *   idle     -> dropzone (file input, drag/drop, sample photo)
 *   crop     -> the photo with draggable pins BEFORE any analysis
 *   progress -> staged analysis (vision-loading/cached/retry, six stage rows)
 *   results  -> side-by-side photo + recovered quilt, confidence and lightbox
 * Each screen and component lives in ./photo/ with its own stylesheet (C1b).
 */
import { useProject } from "../state/project";
import { usePhoto } from "../state/photo";
import { CropScreen } from "./photo/CropScreen";
import { DropzoneScreen } from "./photo/DropzoneScreen";
import { ProgressScreen } from "./photo/ProgressScreen";
import { ResultsScreen } from "./photo/ResultsScreen";

export default function PhotoFlow() {
  const { goHome } = useProject();
  const photo = usePhoto();

  switch (photo.state) {
    case "crop":
      return <CropScreen photo={photo} />;
    case "progress":
      return <ProgressScreen photo={photo} />;
    case "results":
      return <ResultsScreen photo={photo} />;
    case "idle":
    default:
      return <DropzoneScreen photo={photo} onHome={goHome} />;
  }
}
