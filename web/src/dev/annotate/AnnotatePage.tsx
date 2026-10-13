/**
 * The dev annotate page (C3a, issue #149; plan section 8.2): Jake confirms
 * corpus truth here before the product confirm screen exists (Critique:
 * CR-sequencing-16), and the pin drill records unprompted placements for D10
 * (plan section 9, item 4). It loads a photo and, optionally, its annotation,
 * and saves verified-jake claims for the frame, the counts and the
 * construction class. It never calls the engine, and Pages never publishes
 * it (web/scripts/compose-site.mjs).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { BorderBand, Corners, Counts, Point } from "../../engine/contract";
import { bandHandles, bandTotal, fieldQuad, roundWidth, widthFromHandle, type BandSide } from "../../confirm/bands";
import { BandsControl } from "../../confirm/BandsControl";
import { CountsPanel, type CountInput } from "../../confirm/CountsPanel";
import { fromCounts, seedAxis, seedFromSquare, toCounts, type AxisCount } from "../../confirm/counts";
import {
  CORNER_LABELS,
  CORNER_NAMES,
  cornersToQuad,
  quadProblem,
  quadToCorners,
  toRequestFrame,
  type FrameMode,
} from "../../confirm/frame";
import { applyHomography, snapToPixel, squareToQuad, type Size } from "../../confirm/geometry";
import { GridOverlay } from "../../confirm/GridOverlay";
import { PinLayer, type PinInput, type PinSpec } from "../../confirm/PinLayer";
import {
  annotatedFrame,
  aspectMatches,
  AnnotationError,
  CLASS_LABELS,
  CONSTRUCTION_CLASSES,
  frameProvenances,
  isNoBorderFrame,
  newAnnotation,
  parseAnnotation,
  photoProblem,
  photoStem,
  sameStem,
  saveProblems,
  serializeAnnotation,
  startingValues,
  withVerified,
  type Annotation,
  type ConstructionClass,
  type Draft,
} from "./annotation";
import {
  createDrill,
  drillStart,
  recordBands,
  recordCounts,
  recordPin,
  serializeDrill,
  type DeviceInfo,
  type DrillLog,
} from "./drill";
import { withoutOrientation } from "./orientation";
import { sha256Hex } from "./sha256";
import "./annotate.css";

type Mode = "verify" | "drill";

interface Photo {
  url: string;
  name: string;
  natural: Size | null;
  sha256: string | null;
}

/** What ending the drill puts back: the verify edits made before it started. */
interface VerifyState {
  draft: Draft;
  fieldVisible: boolean;
  frameMode: FrameMode;
}

const sameCounts = (a: Counts, b: Counts) =>
  (Object.keys(a) as (keyof Counts)[]).every((key) => a[key] === b[key]);

/** 3/4 in to 4 in in 1/4 in steps, in eighths: CELL_MIN 6 to CELL_MAX 32 (plan A10). */
const SQUARE_SIZES = Array.from({ length: 14 }, (_, i) => 6 + 2 * i);

function inchLabel(eighths: number): string {
  const whole = Math.floor(eighths / 8);
  const quarters = (eighths % 8) / 2;
  const part = ["", "1/4", "1/2", "3/4"][quarters];
  return `${whole ? whole : ""}${whole && part ? " " : ""}${part} in`;
}

function draftFrom(annotation: Annotation | null, canvas: [number, number], provenance?: string) {
  const empty = drillStart(canvas);
  if (!annotation) return { draft: empty, fieldVisible: false, from: null as string | null, frameMode: "outer_edge" as FrameMode };
  const start = startingValues(annotation, provenance);
  const counts = start.counts ? fromCounts(start.counts) : { across: empty.across, down: empty.down };
  const draft: Draft = {
    outer: start.frame?.outer_edge.corners ?? empty.outer,
    field: start.frame?.field?.corners ?? null,
    bands: (start.frame?.outer_edge.bands ?? []).map((band) => ({ width_squares: band.width_squares })),
    across: counts.across,
    down: counts.down,
    constructionClass: start.constructionClass,
  };
  // A no-border frame reopens as field corners, or its field pins would sit
  // on top of the outer pins and an edit would reach only one of the two.
  if (start.frame && isNoBorderFrame(start.frame)) {
    return { draft, fieldVisible: false, from: start.provenance, frameMode: "field" as FrameMode };
  }
  return { draft, fieldVisible: draft.field !== null, from: start.provenance, frameMode: "outer_edge" as FrameMode };
}

function deviceInfo(): DeviceInfo {
  return {
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    device_pixel_ratio: window.devicePixelRatio || 1,
    pointer: window.matchMedia("(pointer: coarse)").matches ? "coarse" : "fine",
  };
}

/** Hands the browser a file to save; it lands where the browser saves files. */
function saveText(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  // WebKit fails a save whose blob URL is revoked too soon (bugs.webkit.org 211234).
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Hands over the chosen file and clears the input, so choosing the same file again still fires a change. */
function takeFile(input: HTMLInputElement, open: (file: File) => void) {
  const file = input.files?.[0];
  input.value = "";
  if (file) open(file);
}

export function AnnotatePage() {
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [annotation, setAnnotation] = useState<Annotation | null>(null);
  const [photoPath, setPhotoPath] = useState("");
  const [mode, setMode] = useState<Mode>("verify");
  const [frameMode, setFrameMode] = useState<FrameMode>("outer_edge");
  const [fieldVisible, setFieldVisible] = useState(false);
  const [startFrom, setStartFrom] = useState<string | undefined>(undefined);
  const [seededFrom, setSeededFrom] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeBand, setActiveBand] = useState<number | null>(null);
  const [square, setSquare] = useState<[Point, Point] | null>(null);
  const [squareEighths, setSquareEighths] = useState<number | null>(null);
  const [drill, setDrill] = useState<DrillLog | null>(null);
  const drillStartMs = useRef(0);
  // The counts the drill last recorded, so typing records each entry once.
  const drillCounts = useRef<Counts | null>(null);
  const beforeDrill = useRef<VerifyState | null>(null);
  // Each photo opened counts up, so a slow read of an earlier one is dropped.
  const photoSeq = useRef(0);
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  const canvas: [number, number] | null = annotation
    ? annotation.canvas
    : photo?.natural
      ? [photo.natural.width, photo.natural.height]
      : null;
  const shapeOk = !annotation || !photo?.natural || aspectMatches(annotation.canvas, photo.natural);
  const mismatch =
    annotation && photo?.natural && photo.sha256 ? photoProblem(annotation, photo.natural, photo.sha256) : null;
  const ready = Boolean(photo?.natural && canvas && shapeOk && !mismatch && draft);

  // Opening a photo, an annotation or another starting claim resets the
  // draft. Starting and ending a drill set it themselves.
  const natural = photo?.natural ?? null;
  useEffect(() => {
    if (!natural) return;
    if (annotation && !aspectMatches(annotation.canvas, natural)) return;
    const start = draftFrom(annotation, annotation ? annotation.canvas : [natural.width, natural.height], startFrom);
    setDraft(start.draft);
    setFieldVisible(start.fieldVisible);
    setSeededFrom(start.from);
    setFrameMode(start.frameMode);
    setActiveBand(null);
    setSquare(null);
  }, [annotation, natural, startFrom]);

  // Revoke a photo's object URL only once another photo replaces it.
  const photoUrl = photo?.url;
  useEffect(() => () => {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
  }, [photoUrl]);

  const identity = canvas
    ? {
        photo: annotation?.photo ?? photoPath,
        sha256: annotation?.sha256 ?? photo?.sha256 ?? "",
        canvas,
      }
    : null;

  // The quad the pins frame: the outer edge, or the field in field mode.
  const pinned: Corners | null = draft ? (frameMode === "field" ? draft.field : draft.outer) : null;
  const pinnedProblem = pinned ? quadProblem(pinned) : null;
  const homography = useMemo(
    () => (pinned && !pinnedProblem ? squareToQuad(cornersToQuad(pinned)) : null),
    [pinned, pinnedProblem],
  );
  const cols = draft ? draft.across.blocks * draft.across.squaresPerBlock : 1;
  const rows = draft ? draft.down.blocks * draft.down.squaresPerBlock : 1;
  const bands = draft && frameMode === "outer_edge" ? draft.bands : [];

  // Snapped like every pin, so a derived corner saves as a whole pixel.
  const derivedField = (d: Draft): Corners => {
    if (!homography || frameMode !== "outer_edge" || !canvas) return d.outer;
    const size = { width: canvas[0], height: canvas[1] };
    const [tl, tr, br, bl] = fieldQuad(homography, cols, rows, d.bands).map((p) => snapToPixel(p, size));
    return quadToCorners([tl, tr, br, bl]);
  };

  const elapsed = () => Math.round(performance.now() - drillStartMs.current);

  const onPhoto = async (file: File) => {
    const seq = ++photoSeq.current;
    setError(null);
    setStatus(null);
    setProblems([]);
    if (mode === "drill") setMode("verify");
    setDrill(null);
    beforeDrill.current = null;
    setDraft(null);
    let bytes: Uint8Array<ArrayBuffer>;
    try {
      bytes = new Uint8Array(await file.arrayBuffer());
    } catch {
      if (seq === photoSeq.current) setError("This photo could not be read.");
      return;
    }
    if (seq !== photoSeq.current) return;
    // Pins index the pixels as the file stores them, so the page shows them
    // that way whatever the EXIF orientation says (orientation.ts).
    const url = URL.createObjectURL(new Blob([withoutOrientation(bytes)], { type: file.type }));
    setPhoto({ url, name: file.name, natural: null, sha256: null });
    // An annotation names its photo; keeping it for another photo would save
    // that photo's pins under the first one's identity. A photo with the
    // same stem is checked by its sha256 once that is known (photoProblem).
    const keep = annotation !== null && sameStem(annotation.photo, file.name);
    if (annotation && !keep) {
      setAnnotation(null);
      setStatus(`Closed the annotation for ${annotation.photo}: it names another photo.`);
    }
    if (!keep) setPhotoPath(file.name);
    // Yield first, so the photo shows while a large file hashes.
    await new Promise((resolve) => setTimeout(resolve, 0));
    if (seq !== photoSeq.current) return;
    const sha = sha256Hex(bytes);
    setPhoto((p) => (p && p.url === url ? { ...p, sha256: sha } : p));
  };

  const onAnnotationFile = async (file: File) => {
    setError(null);
    setStatus(null);
    setProblems([]);
    try {
      const parsed = parseAnnotation(await file.text());
      if (photo && !sameStem(parsed.photo, photo.name)) {
        setError(`This annotation names ${parsed.photo}, but the open photo is ${photo.name}. Open the photo it names first.`);
        return;
      }
      if (mode === "drill") setMode("verify");
      setDrill(null);
      beforeDrill.current = null;
      setStartFrom(undefined);
      setAnnotation(parsed);
    } catch (err) {
      setError(err instanceof AnnotationError ? err.message : "This annotation could not be read.");
    }
  };

  /** One counts record per entry: a counts value the drill has not recorded last. */
  const recordCountsEntry = (counts: Counts) => {
    if (!drill || (drillCounts.current && sameCounts(drillCounts.current, counts))) return;
    drillCounts.current = counts;
    setDrill((log) => log && recordCounts(log, counts, elapsed()));
  };

  // Typing redraws the grid at once but records only when the field settles,
  // so "12" is one entry, not "1" and then "12".
  const setCounts = (across: AxisCount, down: AxisCount, input: CountInput = "step") => {
    setDraft((d) => d && { ...d, across, down });
    if (input === "step") recordCountsEntry(toCounts(across, down));
  };

  const settleCounts = () => {
    if (draft) recordCountsEntry(toCounts(draft.across, draft.down));
  };

  const setBands = (next: BorderBand[]) => {
    setDraft((d) => d && { ...d, bands: next });
    if (drill) setDrill((log) => log && recordBands(log, next, elapsed()));
  };

  /** The active band's width read from its handle at point, or null when the point gives none. */
  const widthAt = (side: string, point: Point): number | null => {
    if (!homography || activeBand === null || !draft) return null;
    const width = widthFromHandle(homography, side as BandSide, point, cols, rows, draft.bands, activeBand);
    return width === null ? null : roundWidth(width);
  };
  const withWidth = (bands: BorderBand[], width: number) =>
    bands.map((b, i) => (i === activeBand ? { width_squares: width } : b));

  const onMove = (id: string, point: Point) => {
    const [set, part] = id.split(".");
    if (set === "outer" || set === "field") {
      setDraft((d) => {
        if (!d) return d;
        const key = set === "outer" ? "outer" : "field";
        const base = key === "field" ? (d.field ?? derivedField(d)) : d.outer;
        return { ...d, [key]: { ...base, [part]: point } };
      });
    } else if (set === "band") {
      const width = widthAt(part, point);
      if (width !== null) setDraft((d) => d && { ...d, bands: withWidth(d.bands, width) });
    } else if (set === "square") {
      setSquare((s) => s && (part === "a" ? [point, s[1]] : [s[0], point]));
    }
  };

  const onPlace = (id: string, point: Point, input: PinInput) => {
    if (!drill) return;
    if (id.startsWith("outer.") || id.startsWith("field.")) {
      setDrill((log) => log && recordPin(log, id, point, input, elapsed()));
    } else if (id.startsWith("band.") && draft) {
      const width = widthAt(id.split(".")[1], point);
      if (width !== null) setDrill((log) => log && recordBands(log, withWidth(draft.bands, width), elapsed()));
    }
  };

  const startDrill = () => {
    if (!identity || !canvas || !identity.sha256 || !draft) return;
    beforeDrill.current = { draft, fieldVisible, frameMode };
    const start = drillStart(canvas);
    setMode("drill");
    setDraft(frameMode === "field" ? { ...start, field: start.outer } : start);
    setFieldVisible(false);
    setActiveBand(null);
    setSquare(null);
    setDrill(createDrill(identity, frameMode, deviceInfo(), new Date().toISOString()));
    drillCounts.current = toCounts(start.across, start.down);
    drillStartMs.current = performance.now();
    setStatus(null);
    setProblems([]);
  };

  // Ending the drill puts back the verify edits from before it, saved or not.
  const stopDrill = () => {
    const saved = beforeDrill.current;
    beforeDrill.current = null;
    setMode("verify");
    setDrill(null);
    setActiveBand(null);
    setSquare(null);
    if (saved) {
      setDraft(saved.draft);
      setFieldVisible(saved.fieldVisible);
      setFrameMode(saved.frameMode);
    }
  };

  const changeFrameMode = (next: FrameMode) => {
    if (!draft) return;
    if (next === "field") setDraft({ ...draft, field: draft.field ?? derivedField(draft) });
    setFrameMode(next);
    setActiveBand(null);
  };

  const toggleField = (on: boolean) => {
    if (!draft) return;
    setFieldVisible(on);
    setDraft({ ...draft, field: on ? (draft.field ?? derivedField(draft)) : null });
  };

  const startSquare = () => {
    if (!homography || !canvas) return;
    const size = { width: canvas[0], height: canvas[1] };
    const range = frameMode === "outer_edge" ? bandTotal(bands) : 0;
    // Start the two pins one square apart at the current counts, near the middle.
    // At most a tenth of the frame, so at 1 x 1 the pins do not start on the corners.
    const du = Math.min(0.1, 1 / (cols + 2 * range));
    const dv = Math.min(0.1, 1 / (rows + 2 * range));
    setSquare([
      snapToPixel(applyHomography(homography, 0.5 - du / 2, 0.5 - dv / 2), size),
      snapToPixel(applyHomography(homography, 0.5 + du / 2, 0.5 + dv / 2), size),
    ]);
  };

  const applySquare = () => {
    if (!square || !homography || !draft) return;
    if (Math.abs(square[0].x - square[1].x) < 2 || Math.abs(square[0].y - square[1].y) < 2) {
      setError("Drag the two square pins to opposite corners of one square.");
      return;
    }
    const seeded = seedFromSquare(homography, square, frameMode === "outer_edge" ? bandTotal(draft.bands) : 0);
    setCounts(seedAxis(draft.across, seeded.across), seedAxis(draft.down, seeded.down));
    setSquare(null);
    setError(null);
  };

  const frameValue = draft
    ? annotatedFrame(
        frameMode,
        frameMode === "field" ? (draft.field ?? draft.outer) : draft.outer,
        draft.bands,
        frameMode === "outer_edge" && fieldVisible ? draft.field : null,
      )
    : null;

  const save = () => {
    setStatus(null);
    if (!draft || !frameValue || !identity || !canvas) return;
    if (mode === "drill") {
      if (!drill) return;
      const name = `${photoStem(identity.photo)}.drill.json`;
      saveText(name, serializeDrill(drill));
      setStatus(`Saved ${name} with ${drill.records.length} records.`);
      return;
    }
    const verified = { frame: frameValue, counts: toCounts(draft.across, draft.down), constructionClass: draft.constructionClass };
    const found = saveProblems(verified, canvas);
    if (!identity.photo) found.push("Name the photo by its manifest path before you save.");
    setProblems(found);
    if (found.length || !draft.constructionClass) return;
    const base = annotation ?? newAnnotation(identity.photo, identity.sha256, canvas);
    const name = `${photoStem(identity.photo)}.json`;
    saveText(name, serializeAnnotation(withVerified(base, { ...verified, constructionClass: draft.constructionClass })));
    setStatus(`Saved ${name}.`);
  };

  const pins: PinSpec[] = [];
  if (draft && pinned) {
    const set = frameMode === "field" ? "field" : "outer";
    for (const name of CORNER_NAMES) {
      pins.push({
        id: `${set}.${name}`,
        point: pinned[name],
        label: `${set === "outer" ? "Outer edge" : "Field"}, ${CORNER_LABELS[name]}`,
        tone: set === "outer" ? "corner" : "field",
      });
    }
    if (frameMode === "outer_edge" && fieldVisible && draft.field) {
      for (const name of CORNER_NAMES) {
        pins.push({ id: `field.${name}`, point: draft.field[name], label: `Field, ${CORNER_LABELS[name]}`, tone: "field" });
      }
    }
    if (homography && activeBand !== null && activeBand < bands.length) {
      const handles = bandHandles(homography, cols, rows, bands, activeBand);
      for (const side of ["top", "right", "bottom", "left"] as const) {
        pins.push({ id: `band.${side}`, point: handles[side], label: `Band ${activeBand + 1} inner line, ${side}`, tone: "band" });
      }
    }
    if (square) {
      pins.push({ id: "square.a", point: square[0], label: "One square, first corner", tone: "square" });
      pins.push({ id: "square.b", point: square[1], label: "One square, opposite corner", tone: "square" });
    }
  }

  const requestFrame = draft && pinned ? toRequestFrame(frameMode, pinned, bands) : null;
  // The page hashes every photo, an annotated one too, to check it is the one
  // the annotation names.
  const hashing = Boolean(photo && !photo.sha256);

  return (
    <main className="an-page">
      <header className="an-head">
        <h1 className="an-title">Annotate (dev page)</h1>
        <p className="an-note">
          Not part of the app. Confirm a photo's frame, bands, counts and class, or run the pin drill. Saved
          files go where the browser saves files; nothing leaves this device.
        </p>
      </header>

      <section className="an-files" aria-label="Files">
        <label className="an-file">
          <span>Photo</span>
          <input type="file" accept="image/*" data-testid="photo-input" onChange={(e) => takeFile(e.target, onPhoto)} />
        </label>
        <label className="an-file">
          <span>Annotation (optional)</span>
          <input
            type="file"
            accept="application/json,.json"
            data-testid="annotation-input"
            onChange={(e) => takeFile(e.target, onAnnotationFile)}
          />
        </label>
        <label className="an-file">
          <span>Photo path (the manifest file value)</span>
          <input
            type="text"
            data-testid="photo-path"
            value={annotation?.photo ?? photoPath}
            readOnly={Boolean(annotation)}
            onChange={(e) => setPhotoPath(e.target.value)}
          />
        </label>
        <p className="an-ident" data-testid="identity">
          {identity
            ? `Canvas ${identity.canvas[0]} x ${identity.canvas[1]} px; sha256 ${hashing ? "being computed" : identity.sha256 || "unknown"}`
            : "Open a photo to begin."}
        </p>
      </section>

      {error && (
        <p className="an-error" role="alert" data-testid="error">
          {error}
        </p>
      )}
      {!shapeOk && canvas && (
        <p className="an-error" role="alert" data-testid="shape-error">
          This photo is not the shape of the annotation's canvas ({canvas[0]} x {canvas[1]} px). Open the photo the
          annotation names, without rotating it.
        </p>
      )}

      {/* The stage renders before the photo's size is known: its img element is what measures it. */}
      {mismatch && (
        <p className="an-error" role="alert" data-testid="sha-error">
          {mismatch} Open the photo the annotation names.
        </p>
      )}

      {photo && shapeOk && !mismatch && (
        <div className="an-main">
          <div className="an-stage">
            <PinLayer
              src={photo.url}
              canvas={{ width: canvas?.[0] ?? 1, height: canvas?.[1] ?? 1 }}
              pins={ready ? pins : []}
              activeId={activeId}
              onActivate={setActiveId}
              onMove={onMove}
              onPlace={onPlace}
              onImageLoad={(natural) => setPhoto((p) => p && { ...p, natural })}
              onImageError={() => setError("This file is not an image the browser can open.")}
              overlay={
                homography && draft ? (
                  <GridOverlay
                    homography={homography}
                    across={draft.across}
                    down={draft.down}
                    bands={bands}
                    activeBand={activeBand}
                    pinnedField={frameMode === "outer_edge" && fieldVisible && draft.field ? cornersToQuad(draft.field) : null}
                  />
                ) : null
              }
            />
            {pinnedProblem && <p className="an-error">{pinnedProblem}</p>}
          </div>

          {draft && (
            <div className="an-controls">
              <section className="an-group" aria-label="Mode">
                <div className="an-row">
                  {mode === "verify" ? (
                    <button type="button" className="cf-btn" data-testid="drill-start" disabled={hashing} onClick={startDrill}>
                      Start the pin drill
                    </button>
                  ) : (
                    <button type="button" className="cf-btn" data-testid="drill-stop" onClick={stopDrill}>
                      End the drill
                    </button>
                  )}
                  <span className="an-mode" data-testid="mode">
                    {mode === "drill"
                      ? `Pin drill: the annotation is hidden; ${drill?.records.length ?? 0} records`
                      : seededFrom
                        ? `Verifying, starting from ${seededFrom}`
                        : "Verifying a new photo"}
                  </span>
                </div>
                {mode === "verify" && annotation && frameProvenances(annotation).length > 1 && (
                  <label className="an-field">
                    <span>Start from</span>
                    <select data-testid="start-from" value={seededFrom ?? ""} onChange={(e) => setStartFrom(e.target.value)}>
                      {frameProvenances(annotation).map((code) => (
                        <option key={code} value={code}>
                          {code}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </section>

              <section className="an-group" aria-label="Frame">
                <label className="an-field">
                  <span>Frame</span>
                  <select
                    data-testid="frame-mode"
                    value={frameMode}
                    disabled={mode === "drill"}
                    onChange={(e) => changeFrameMode(e.target.value as FrameMode)}
                  >
                    <option value="outer_edge">Outer edge and border bands</option>
                    <option value="field">Field corners, no border</option>
                  </select>
                </label>
                {frameMode === "outer_edge" && mode === "verify" && (
                  <label className="an-check">
                    <input
                      type="checkbox"
                      data-testid="field-visible"
                      checked={fieldVisible}
                      onChange={(e) => toggleField(e.target.checked)}
                    />
                    <span>The field corners show: pin them too</span>
                  </label>
                )}
              </section>

              {frameMode === "outer_edge" && (
                <section className="an-group" aria-label="Square size and bands">
                  <label className="an-field">
                    <span>Finished square size</span>
                    <select
                      data-testid="square-size"
                      value={squareEighths ?? ""}
                      onChange={(e) => setSquareEighths(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">Not set</option>
                      {SQUARE_SIZES.map((eighths) => (
                        <option key={eighths} value={eighths}>
                          {inchLabel(eighths)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <BandsControl
                    bands={draft.bands}
                    onChange={setBands}
                    activeBand={activeBand}
                    onSelect={setActiveBand}
                    squareEighths={squareEighths}
                  />
                </section>
              )}

              <section className="an-group" aria-label="Counts">
                <CountsPanel
                  across={draft.across}
                  down={draft.down}
                  onChange={setCounts}
                  onSettle={settleCounts}
                  onMeasure={square ? undefined : startSquare}
                />
                {square && (
                  <div className="an-row">
                    <span className="an-note">Drag the two green pins to opposite corners of one square.</span>
                    <button type="button" className="cf-btn" data-testid="square-use" onClick={applySquare}>
                      Use this square
                    </button>
                    <button type="button" className="cf-btn" data-testid="square-cancel" onClick={() => setSquare(null)}>
                      Cancel
                    </button>
                  </div>
                )}
              </section>

              {mode === "verify" && (
                <section className="an-group" aria-label="Construction class">
                  <label className="an-field">
                    <span>Construction class</span>
                    <select
                      data-testid="construction-class"
                      value={draft.constructionClass ?? ""}
                      onChange={(e) =>
                        setDraft({ ...draft, constructionClass: (e.target.value || null) as ConstructionClass | null })
                      }
                    >
                      <option value="">Choose a class</option>
                      {CONSTRUCTION_CLASSES.map((cls) => (
                        <option key={cls} value={cls}>
                          {CLASS_LABELS[cls]}
                        </option>
                      ))}
                    </select>
                  </label>
                </section>
              )}

              <section className="an-group an-save" aria-label="Save">
                <button type="button" className="cf-btn an-primary" data-testid="save" disabled={hashing} onClick={save}>
                  {mode === "drill" ? "Save drill records" : "Save annotation"}
                </button>
                {status && (
                  <p className="an-status" role="status" data-testid="status">
                    {status}
                  </p>
                )}
                {problems.length > 0 && (
                  <ul className="an-error" role="alert" data-testid="problems">
                    {problems.map((problem) => (
                      <li key={problem}>{problem}</li>
                    ))}
                  </ul>
                )}
              </section>

              {requestFrame && (
                <details className="an-group">
                  <summary>Read request frame (E1b shape)</summary>
                  <pre className="an-pre" data-testid="request-frame">
                    {JSON.stringify(requestFrame, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
