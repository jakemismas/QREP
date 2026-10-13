/**
 * Your pattern's Retry through the hook itself (C2a, issue #96):
 * usePatternState routes Retry through retryPattern, so after a failure of
 * the worker itself the engine restarts before the call goes again, for the
 * PDF and for the fabric census alike, and after a bridge error the call goes
 * to the same worker with no restart. Rendered to a string in Node, with no
 * DOM: the render captures the hook's API, whose callbacks then drive the PDF
 * controller and the census queue (both live in refs) against a scripted fake
 * worker. A server render drops state updates made after it, so the test
 * reads the engine's side: the workers made, the calls each was sent, and the
 * file saved.
 */
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EngineClient, type WorkerLike } from "../engine/rpc";
import type { Engine } from "../engine/useEngine";
import type { ModelSummary, QuiltModel } from "../model/types";
import { CensusQueue, type ModelApi } from "../state/model";
import { usePatternState, type YourPatternApi } from "../state/pattern";

const fakes = vi.hoisted(() => ({
  engine: null as unknown,
  toasts: [] as [string, string][],
}));

vi.mock("../engine/useEngine", () => ({ useEngine: () => fakes.engine }));
vi.mock("../ui", () => ({
  useToast: () => ({ push: (message: string, kind: string) => fakes.toasts.push([message, kind]) }),
}));

interface Sent {
  type: string;
  id?: number;
  method?: string;
  args?: unknown[];
}

class FakeWorker implements WorkerLike {
  sent: Sent[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;

  postMessage(message: unknown): void {
    this.sent.push(message as Sent);
  }

  terminate(): void {}

  emit(message: unknown): void {
    this.onmessage?.({ data: message } as MessageEvent);
  }

  calls(): Sent[] {
    return this.sent.filter((m) => m.type === "call");
  }

  respond(id: number, envelope: unknown): void {
    this.emit({ type: "result", id, envelope });
  }
}

function bootedClient(): { client: EngineClient; workers: FakeWorker[] } {
  const workers: FakeWorker[] = [];
  const client = new EngineClient(() => {
    const worker = new FakeWorker();
    workers.push(worker);
    return worker;
  });
  client.start();
  workers[0].emit({ type: "boot-done" });
  return { client, workers };
}

/** The Engine the app builds over its client (engine/useEngine.tsx). */
function engineFor(client: EngineClient): Engine {
  return {
    retry: () => client.restart(),
    restart: () => client.restart(),
    validate: (json) => client.call<ModelSummary>("validate", json),
    call: (method, ...args) => client.call(method, ...args),
    onVision: () => () => {},
    prefetchVision: () => {},
  };
}

const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

// worker.ts's catch in serve() posts this sentence when the worker itself
// fails a call (patternPdf.ts isWorkerFailure).
const WORKER_FAILED = { ok: false, error: { kind: "internal", message: "engine call failed in the worker" } };
// The bridge's own internal error (qrep/bridge.py), which leaves the worker sound.
const BRIDGE_FAILED = {
  ok: false,
  error: { kind: "internal", message: "internal engine error; see the browser console log" },
};

const MODEL: QuiltModel = {
  schema_version: "1.0",
  metadata: { name: "Recovered quilt" },
  palette: { fabrics: [{ id: "f0", name: "Fabric 1", color: "#336699" }] },
  center: { rows: 1, cols: 1, cell_size: 16, cells: [["f0"]] },
  borders: [],
  binding: { fabric_id: "f0" },
};
const MODEL_JSON = JSON.stringify(MODEL);
const CENSUS: ModelSummary = {
  name: "Recovered quilt",
  rows: 1,
  cols: 1,
  fabric_count: 1,
  fabrics: [{ id: "f0", name: "Fabric 1", color: "#336699", cell_count: 1 }],
  finished_width: 16,
  finished_height: 16,
  batting_width: 80,
  batting_height: 80,
  usable_width: 336,
};
const PDF_B64 = btoa("%PDF-1.4\n% a tiny stand-in pattern\n");
const SUMMARY = { method: "strip", method_reason: "Blocks repeat.", fabrics: [] };

function censusFor(client: EngineClient): { census: CensusQueue; summaries: ModelSummary[] } {
  const summaries: ModelSummary[] = [];
  const census = new CensusQueue({
    validate: (json) => client.call<ModelSummary>("validate", json),
    onSummary: (summary) => summaries.push(summary),
    onError: () => {},
    onFailedChange: () => {},
  });
  return { census, summaries };
}

function modelApi(census: CensusQueue): ModelApi {
  return {
    model: MODEL,
    name: "Recovered quilt",
    summary: null,
    replaceModel: () => {},
    setName: () => {},
    latestModel: () => MODEL,
    opened: 1,
    latestOpened: () => 1,
    censusFailed: census.failed,
    censusRequest: census,
  };
}

/** Render the hook once and hand back Your pattern's API. */
function yourPatternFor(model: ModelApi): YourPatternApi {
  let captured: YourPatternApi | null = null;
  function Probe() {
    captured = usePatternState(model).api.yourPattern;
    return null;
  }
  renderToString(<Probe />);
  if (captured === null) throw new Error("the hook did not render");
  return captured;
}

// The PDF save makes an anchor and clicks it (state/pattern.tsx triggerBlob);
// this stand-in document records the file name each click saves under.
let saved: string[] = [];

beforeEach(() => {
  fakes.toasts = [];
  saved = [];
  vi.stubGlobal("document", {
    createElement: () => {
      const anchor = { href: "", download: "", click: () => saved.push(anchor.download), remove: () => {} };
      return anchor;
    },
    body: { appendChild: () => {} },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Your pattern's Retry, through usePatternState", () => {
  it("restarts the engine after the worker itself failed the PDF, and the PDF saves from the new worker", async () => {
    const { client, workers } = bootedClient();
    fakes.engine = engineFor(client);
    const { census } = censusFor(client);
    const yourPattern = yourPatternFor(modelApi(census));

    yourPattern.savePdf();
    await settle();
    // Hand count: the census was never asked for, so the one call is the PDF's.
    expect(workers[0].calls()).toHaveLength(1);
    expect(workers[0].calls()[0].method).toBe("export_pattern");
    expect(workers[0].calls()[0].args).toEqual([MODEL_JSON]);
    workers[0].respond(workers[0].calls()[0].id!, WORKER_FAILED);
    await settle();

    yourPattern.retry("pdf");
    await settle();
    // Hand count: the Retry restarted the engine once, so there are two
    // workers, and the broken one was sent nothing more.
    expect(workers).toHaveLength(2);
    expect(workers[0].calls()).toHaveLength(1);

    workers[1].emit({ type: "boot-done" });
    await settle();
    expect(workers[1].calls()).toHaveLength(1);
    expect(workers[1].calls()[0].method).toBe("export_pattern");
    expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
    workers[1].respond(workers[1].calls()[0].id!, {
      ok: true,
      result: { outcome: "pattern_ready", pdf_b64: PDF_B64, summary: SUMMARY },
    });
    await settle();
    // The file name is the model's name in kebab case, with no census to
    // name it: "Recovered quilt" -> "recovered-quilt" -> recovered-quilt.pdf.
    expect(saved).toEqual(["recovered-quilt.pdf"]);
    expect(fakes.toasts).toEqual([["Saved: your pattern file is ready.", "success"]]);
  });

  // The census's own Retry, and the summary's: in the broken-worker case the
  // summary fails after the census, and its line shows first.
  for (const action of ["census", "summary"] as const) {
    it(`restarts the engine on the ${action}'s Retry after the worker itself failed the census, and the census lands from the new worker`, async () => {
      const { client, workers } = bootedClient();
      fakes.engine = engineFor(client);
      const { census, summaries } = censusFor(client);
      const yourPattern = yourPatternFor(modelApi(census));

      census.request(MODEL_JSON);
      await settle();
      workers[0].respond(workers[0].calls()[0].id!, WORKER_FAILED);
      await settle();
      expect(census.failed).toBe(true);

      yourPattern.retry(action);
      await settle();
      // Hand count: one restart, nothing more to the broken worker.
      expect(workers).toHaveLength(2);
      expect(workers[0].calls()).toHaveLength(1);

      workers[1].emit({ type: "boot-done" });
      await settle();
      // Hand count: the one failed validate, sent once to the new worker.
      expect(workers[1].calls()).toHaveLength(1);
      expect(workers[1].calls()[0].method).toBe("validate");
      expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
      workers[1].respond(workers[1].calls()[0].id!, { ok: true, result: CENSUS });
      await settle();
      expect(summaries).toEqual([CENSUS]);
      expect(census.failed).toBe(false);
    });
  }

  it("sends the census again to the same worker after a bridge error, with no restart", async () => {
    const { client, workers } = bootedClient();
    fakes.engine = engineFor(client);
    const { census, summaries } = censusFor(client);
    const yourPattern = yourPatternFor(modelApi(census));

    census.request(MODEL_JSON);
    await settle();
    workers[0].respond(workers[0].calls()[0].id!, BRIDGE_FAILED);
    await settle();

    yourPattern.retry("census");
    await settle();
    // Hand count: no restart, so one worker, holding the failed validate and
    // the Retry's one validate.
    expect(workers).toHaveLength(1);
    expect(workers[0].calls()).toHaveLength(2);
    expect(workers[0].calls()[1].method).toBe("validate");
    workers[0].respond(workers[0].calls()[1].id!, { ok: true, result: CENSUS });
    await settle();
    expect(summaries).toEqual([CENSUS]);
  });
});
