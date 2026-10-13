/**
 * Your pattern's engine calls (C2a, issue #96): the PDF controller, the
 * summary loader and the census queue, driven through EngineClient by a
 * scripted fake worker (the FakeWorker shape from engine/rpc.test.ts). No
 * DOM: the controller hands the PDF to a save callback, which the screen
 * wires to a file save.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { EngineClient, EngineError, type WorkerLike } from "../engine/rpc";
import type { ModelSummary } from "../model/types";
import { CensusQueue } from "../state/model";
import { base64ToArrayBuffer, patternFileName, patternPdfName } from "../state/pattern";
import {
  isWorkerFailure,
  PatternPdfController,
  PatternSummaryLoader,
  retryPattern,
  type CensusTarget,
  type PdfView,
  type SummaryView,
} from "./patternPdf";

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

  bootDone(): void {
    this.emit({ type: "boot-done" });
  }

  respond(id: number, envelope: unknown): void {
    this.emit({ type: "result", id, envelope });
  }

  calls(): Sent[] {
    return this.sent.filter((m) => m.type === "call");
  }
}

/** A client whose first boot failed, as when the engine's files do not load;
 * client.restart() is what every Retry runs (engine.retry()): Your pattern's
 * and the header engine chip's alike. */
function failedBootClient(): { client: EngineClient; workers: FakeWorker[] } {
  const workers: FakeWorker[] = [];
  const client = new EngineClient(() => {
    const worker = new FakeWorker();
    workers.push(worker);
    return worker;
  });
  client.start();
  workers[0].emit({ type: "boot-failed", message: "the engine files did not load" });
  return { client, workers };
}

function bootedClient(): { client: EngineClient; worker: FakeWorker; workers: FakeWorker[] } {
  const workers: FakeWorker[] = [];
  const client = new EngineClient(() => {
    const worker = new FakeWorker();
    workers.push(worker);
    return worker;
  });
  client.start();
  workers[0].bootDone();
  return { client, worker: workers[0], workers };
}

// Promise callbacks from the client and the controller run as microtasks; a
// macrotask lets every one of them settle first.
const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

// The plain sentence the ticket asks for on any failure that is not a
// refusal, written out here so a changed constant fails these tests.
const FAILED_SENTENCE = "Your pattern could not be made this time. Try again.";
const MODEL_JSON = '{"metadata":{"name":"Double Irish Chain 75x90"}}';
const FILE = "double-irish-chain-75x90.pdf";
const PDF_B64 = btoa("%PDF-1.4\n% a tiny stand-in pattern\n");
const SUMMARY = { method: "strip", method_reason: "Blocks repeat.", fabrics: [] };

function ready(summary: unknown = SUMMARY) {
  return { ok: true, result: { outcome: "pattern_ready", pdf_b64: PDF_B64, summary } };
}

function makeController(client: EngineClient) {
  const saved: [string, string][] = [];
  const views: PdfView[] = [];
  const controller = new PatternPdfController({
    call: (method, ...args) => client.call(method, ...args),
    save: (pdfB64, filename) => saved.push([pdfB64, filename]),
    onChange: (view) => views.push(view),
  });
  return { controller, saved, views };
}

describe("PatternPdfController", () => {
  it("turns an engine failure into a plain sentence, and Retry makes the pattern", async () => {
    const { client, worker } = bootedClient();
    const { controller, saved } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    expect(controller.view.status).toBe("busy");
    // One call, export_pattern, carrying the model JSON alone: no strategy.
    expect(worker.calls()).toHaveLength(1);
    expect(worker.calls()[0].method).toBe("export_pattern");
    expect(worker.calls()[0].args).toEqual([MODEL_JSON]);

    worker.respond(worker.calls()[0].id!, {
      ok: false,
      error: { kind: "internal", message: "Traceback: ValueError: plan_strip needs a block period" },
    });
    await settle();
    expect(controller.view).toEqual({ status: "failed", message: FAILED_SENTENCE });
    expect(controller.view.message).not.toMatch(/traceback|plan_strip|period/i);
    expect(saved).toEqual([]);

    void controller.retry();
    await settle();
    expect(controller.view.status).toBe("busy");
    expect(worker.calls()).toHaveLength(2);
    expect(worker.calls()[1].args).toEqual([MODEL_JSON]);
    worker.respond(worker.calls()[1].id!, ready());
    await settle();
    expect(controller.view).toEqual({ status: "idle", message: null });
    expect(saved).toEqual([[PDF_B64, FILE]]);
  });

  it("ignores repeat requests while one runs, so only one call is posted", async () => {
    const { client, worker } = bootedClient();
    const { controller, saved, views } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    void controller.start(MODEL_JSON, FILE);
    void controller.start(MODEL_JSON, FILE);
    await settle();
    expect(worker.calls()).toHaveLength(1);
    expect(views.map((view) => view.status)).toEqual(["busy"]);

    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    expect(saved).toEqual([[PDF_B64, FILE]]);
    expect(worker.calls()).toHaveLength(1);
    expect(views.map((view) => view.status)).toEqual(["busy", "idle"]);
  });

  it("shows a refused outcome's reason, which is written for people, as a refusal", async () => {
    const { client, worker } = bootedClient();
    const { controller, saved } = makeController(client);
    const message = "This quilt has too few squares to make a pattern.";

    void controller.start(MODEL_JSON, FILE);
    await settle();
    worker.respond(worker.calls()[0].id!, {
      ok: true,
      result: { outcome: "refused", reason: { code: "too_small", message } },
    });
    await settle();
    // Refused, not failed: the screen offers no Retry, since the same quilt
    // is refused again.
    expect(controller.view).toEqual({ status: "refused", message });
    expect(saved).toEqual([]);
  });

  it("sends a waiting pattern again after any restart, so one Retry saves it", async () => {
    const { client, workers } = failedBootClient();
    const { controller, saved, views } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    expect(controller.view.status).toBe("busy");
    // The boot failed, so nothing reached the worker.
    expect(workers[0].calls()).toHaveLength(0);

    // The restart alone, as the header's Retry runs it: nothing else asks
    // the controller to send again.
    client.restart();
    await settle();
    // The restart rejected the first call and the controller sent it again,
    // so the pattern still reads as being made, never as failed.
    expect(controller.view.status).toBe("busy");
    expect(views.map((view) => view.status)).not.toContain("failed");

    workers[1].bootDone();
    await settle();
    expect(workers[1].calls()).toHaveLength(1);
    expect(workers[1].calls()[0].method).toBe("export_pattern");
    expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
    workers[1].respond(workers[1].calls()[0].id!, ready());
    await settle();
    expect(saved).toEqual([[PDF_B64, FILE]]);
    expect(controller.view).toEqual({ status: "idle", message: null });
  });

  it("sends a call a restart cut off in flight again, to the new engine", async () => {
    const { client, worker, workers } = bootedClient();
    const { controller, saved, views } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    expect(worker.calls()).toHaveLength(1);
    client.restart();
    await settle();
    workers[1].bootDone();
    await settle();
    // Hand count: one call was in flight, the restart rejected it once, and
    // the controller sent it once more: one call on the new worker.
    expect(workers[1].calls()).toHaveLength(1);
    // The old worker's late answer belongs to a call the restart ended.
    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    expect(saved).toEqual([]);
    workers[1].respond(workers[1].calls()[0].id!, ready());
    await settle();
    expect(saved).toEqual([[PDF_B64, FILE]]);
    expect(views.map((view) => view.status)).toEqual(["busy", "idle"]);
  });

  it("sends nothing again after a restart once the pattern is saved or reset", async () => {
    const { client, worker, workers } = bootedClient();
    const { controller, saved } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    client.restart();
    workers[1].bootDone();
    await settle();
    // Saved: no call waited, so the restart rejected none.
    expect(workers[1].calls()).toHaveLength(0);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    controller.reset();
    client.restart();
    workers[2].bootDone();
    await settle();
    // Reset: the rejected call belongs to a request nobody wants now.
    expect(workers[2].calls()).toHaveLength(0);
    expect(saved).toEqual([[PDF_B64, FILE]]);
    expect(controller.view).toEqual({ status: "idle", message: null });
  });

  it("fails plainly on a result that states no outcome, never reading it as success", async () => {
    const { client, worker } = bootedClient();
    const { controller, saved } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    worker.respond(worker.calls()[0].id!, {
      ok: true,
      result: { pdf_b64: PDF_B64, summary: SUMMARY },
    });
    await settle();
    expect(controller.view).toEqual({ status: "failed", message: FAILED_SENTENCE });
    expect(saved).toEqual([]);
  });

  it("drops a pattern that lands after a reset", async () => {
    const { client, worker } = bootedClient();
    const { controller, saved } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    controller.reset();
    expect(controller.view.status).toBe("idle");
    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    expect(saved).toEqual([]);
    expect(controller.view.status).toBe("idle");
  });

  it("saves the decoded PDF under the file name it is given", async () => {
    // Hand: "Double Irish Chain 75x90" lowercased is "double irish chain
    // 75x90"; each run of characters outside a-z and 0-9 (here the three
    // spaces) becomes one hyphen, giving "double-irish-chain-75x90", and
    // the PDF extension follows.
    expect(patternFileName("Double Irish Chain 75x90")).toBe("double-irish-chain-75x90.pdf");

    const { client, worker } = bootedClient();
    const { controller, saved } = makeController(client);
    void controller.start(MODEL_JSON, patternFileName("Double Irish Chain 75x90"));
    await settle();
    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    expect(saved).toHaveLength(1);
    const [pdfB64, filename] = saved[0];
    expect(filename).toBe("double-irish-chain-75x90.pdf");
    const head = new TextDecoder().decode(new Uint8Array(base64ToArrayBuffer(pdfB64)).subarray(0, 5));
    expect(head).toBe("%PDF-");
  });
});

function makeLoader(client: EngineClient) {
  const views: SummaryView[] = [];
  const loader = new PatternSummaryLoader({
    call: (method, ...args) => client.call(method, ...args),
    onChange: (view) => views.push(view),
  });
  return { loader, views };
}

describe("PatternSummaryLoader", () => {
  it("loads the summary once per model and fails plainly with a retry", async () => {
    const { client, worker } = bootedClient();
    const { loader } = makeLoader(client);

    loader.load(MODEL_JSON);
    loader.load(MODEL_JSON);
    await settle();
    expect(loader.view).toEqual({ status: "loading" });
    expect(worker.calls()).toHaveLength(1);
    expect(worker.calls()[0].method).toBe("export_pattern");
    expect(worker.calls()[0].args).toEqual([MODEL_JSON]);

    worker.respond(worker.calls()[0].id!, {
      ok: false,
      error: { kind: "internal", message: "Traceback: KeyError: 'strip'" },
    });
    await settle();
    expect(loader.view).toEqual({ status: "failed", message: FAILED_SENTENCE });

    loader.retry();
    await settle();
    expect(loader.view).toEqual({ status: "loading" });
    worker.respond(worker.calls()[1].id!, ready());
    await settle();
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
  });

  it("drops the summary of a model that was replaced", async () => {
    const { client, worker } = bootedClient();
    const { loader } = makeLoader(client);
    const replaced = '{"metadata":{"name":"Old quilt"}}';
    const oldSummary = { ...SUMMARY, method_reason: "Old reason." };

    loader.load(replaced);
    loader.load(MODEL_JSON);
    await settle();
    // The client runs one call at a time: the replaced model's goes first.
    expect(worker.calls()).toHaveLength(1);
    expect(worker.calls()[0].args).toEqual([replaced]);
    worker.respond(worker.calls()[0].id!, ready(oldSummary));
    await settle();
    expect(loader.view).toEqual({ status: "loading" });

    expect(worker.calls()[1].args).toEqual([MODEL_JSON]);
    worker.respond(worker.calls()[1].id!, ready());
    await settle();
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
  });

  it("shows a refused summary as a refusal", async () => {
    const { client, worker } = bootedClient();
    const { loader } = makeLoader(client);
    const message = "This quilt has too few squares to make a pattern.";

    loader.load(MODEL_JSON);
    await settle();
    worker.respond(worker.calls()[0].id!, {
      ok: true,
      result: { outcome: "refused", reason: { code: "too_small", message } },
    });
    await settle();
    expect(loader.view).toEqual({ status: "refused", message });
  });

  it("loads a summary a restart rejected, with the restart alone, never showing a failure", async () => {
    const { client, workers } = failedBootClient();
    const { loader, views } = makeLoader(client);

    loader.load(MODEL_JSON);
    await settle();
    client.restart();
    await settle();
    expect(loader.view).toEqual({ status: "loading" });
    expect(views.map((view) => view.status)).not.toContain("failed");

    workers[1].bootDone();
    await settle();
    expect(workers[1].calls()).toHaveLength(1);
    expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
    workers[1].respond(workers[1].calls()[0].id!, ready());
    await settle();
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
    expect(views.map((view) => view.status)).toEqual(["loading", "ready"]);
  });

  it("sends a cleared summary nowhere after a restart", async () => {
    const { client, workers } = failedBootClient();
    const { loader } = makeLoader(client);

    loader.load(MODEL_JSON);
    await settle();
    loader.clear();
    client.restart();
    workers[1].bootDone();
    await settle();
    expect(workers[1].calls()).toHaveLength(0);
    expect(loader.view).toEqual({ status: "idle" });
  });

  it("clears to idle and ignores a result that lands after", async () => {
    const { client, worker } = bootedClient();
    const { loader } = makeLoader(client);

    loader.load(MODEL_JSON);
    await settle();
    loader.clear();
    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    expect(loader.view).toEqual({ status: "idle" });
  });
});

describe("Your pattern's waiting calls after an engine restart", () => {
  it("sends a waiting summary and a waiting PDF again once each, and both land", async () => {
    const { client, workers } = failedBootClient();
    const { loader } = makeLoader(client);
    const { controller, saved, views } = makeController(client);

    loader.load(MODEL_JSON);
    void controller.start(MODEL_JSON, FILE);
    await settle();
    expect(workers[0].calls()).toHaveLength(0);

    client.restart();
    await settle();
    workers[1].bootDone();
    await settle();
    // The client runs one call at a time, so the new worker holds the first
    // resend now and the second once the first is answered.
    expect(workers[1].calls()).toHaveLength(1);
    workers[1].respond(workers[1].calls()[0].id!, ready());
    await settle();
    expect(workers[1].calls()).toHaveLength(2);
    workers[1].respond(workers[1].calls()[1].id!, ready());
    await settle();

    // Hand count: two requests waited (the summary, then the PDF), the one
    // restart rejected each once, and each sent once more: two calls on the
    // new worker, both export_pattern with the model JSON alone.
    expect(workers[1].calls()).toHaveLength(2);
    for (const call of workers[1].calls()) {
      expect(call.method).toBe("export_pattern");
      expect(call.args).toEqual([MODEL_JSON]);
    }
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
    expect(saved).toEqual([[PDF_B64, FILE]]);
    expect(views.map((view) => view.status)).toEqual(["busy", "idle"]);
  });

  it("sends each again once per restart, so a second restart adds no extra call", async () => {
    const { client, workers } = failedBootClient();
    const { loader } = makeLoader(client);
    const { controller, saved } = makeController(client);

    loader.load(MODEL_JSON);
    void controller.start(MODEL_JSON, FILE);
    await settle();
    // The first restart's boot fails too, and a second Retry restarts again.
    client.restart();
    await settle();
    workers[1].emit({ type: "boot-failed", message: "the engine files did not load" });
    client.restart();
    await settle();
    workers[2].bootDone();
    await settle();
    workers[2].respond(workers[2].calls()[0].id!, ready());
    await settle();
    workers[2].respond(workers[2].calls()[1].id!, ready());
    await settle();

    // Hand count: after each restart the summary and the PDF each have one
    // call waiting, since a rejection sends one call and nothing else does;
    // the failed boots posted nothing, so the third worker holds exactly two.
    expect(workers[0].calls()).toHaveLength(0);
    expect(workers[1].calls()).toHaveLength(0);
    expect(workers[2].calls()).toHaveLength(2);
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
    expect(saved).toEqual([[PDF_B64, FILE]]);
  });
});

// The worker's own failures, as worker.ts posts them: its catch in serve()
// (kind internal) and its not-booted guard (kind worker). The bridge's one
// internal error carries its own fixed sentence instead (qrep/bridge.py).
const WORKER_FAILED_SENTENCE = "engine call failed in the worker";
const NOT_BOOTED_SENTENCE = "engine is not booted";
const BRIDGE_INTERNAL_SENTENCE = "internal engine error; see the browser console log";

function failure(kind: string, message: string) {
  return { ok: false, error: { kind, message } };
}

// A census that never failed: the Retry cases below that are not about the
// census pass this one.
const NO_CENSUS: CensusTarget = { failed: false, workerDown: false, retry: () => {} };

function targets(
  client: EngineClient,
  loader: PatternSummaryLoader,
  pdf: PatternPdfController,
  census: CensusTarget = NO_CENSUS,
) {
  return { loader, pdf, census, restart: () => client.restart() };
}

describe("Retry after a failed call", () => {
  it("restarts the engine after the worker itself failed the PDF, and the PDF lands on the new worker", async () => {
    const { client, worker, workers } = bootedClient();
    const { loader } = makeLoader(client);
    const { controller, saved } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    worker.respond(worker.calls()[0].id!, failure("internal", WORKER_FAILED_SENTENCE));
    await settle();
    expect(controller.view).toEqual({ status: "failed", message: FAILED_SENTENCE });
    expect(controller.workerDown).toBe(true);

    retryPattern(targets(client, loader, controller), "pdf");
    await settle();
    // The Retry restarted the engine once: a second worker exists, and the
    // broken one was sent nothing more.
    expect(workers).toHaveLength(2);
    expect(worker.calls()).toHaveLength(1);
    expect(controller.view.status).toBe("busy");
    // The new worker has not booted yet, so the call waits in the queue.
    expect(workers[1].calls()).toHaveLength(0);

    workers[1].bootDone();
    await settle();
    // Hand count: one call failed on the first worker and the Retry sent it
    // once more, after the restart: one call on the second worker.
    expect(workers[1].calls()).toHaveLength(1);
    expect(workers[1].calls()[0].method).toBe("export_pattern");
    expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
    workers[1].respond(workers[1].calls()[0].id!, ready());
    await settle();
    expect(saved).toEqual([[PDF_B64, FILE]]);
    expect(controller.view).toEqual({ status: "idle", message: null });
    expect(controller.workerDown).toBe(false);
    expect(workers).toHaveLength(2);
  });

  it("sends a failed summary with the PDF on the one restart, so both land", async () => {
    const { client, worker, workers } = bootedClient();
    const { loader } = makeLoader(client);
    const { controller, saved } = makeController(client);

    loader.load(MODEL_JSON);
    void controller.start(MODEL_JSON, FILE);
    await settle();
    // One call at a time: the summary first, then the PDF; the worker fails both.
    worker.respond(worker.calls()[0].id!, failure("internal", WORKER_FAILED_SENTENCE));
    await settle();
    worker.respond(worker.calls()[1].id!, failure("internal", WORKER_FAILED_SENTENCE));
    await settle();
    expect(loader.view).toEqual({ status: "failed", message: FAILED_SENTENCE });
    expect(controller.view).toEqual({ status: "failed", message: FAILED_SENTENCE });

    // The error line shows the PDF's failure first, so its Retry is the one.
    retryPattern(targets(client, loader, controller), "pdf");
    await settle();
    workers[1].bootDone();
    await settle();
    workers[1].respond(workers[1].calls()[0].id!, ready());
    await settle();
    workers[1].respond(workers[1].calls()[1].id!, ready());
    await settle();

    // Hand count: two calls failed on the first worker, and the one Retry
    // restarted the engine once and sent each once more: two workers, the
    // first holding its two failed calls and the second the two resends.
    expect(workers).toHaveLength(2);
    expect(worker.calls()).toHaveLength(2);
    expect(workers[1].calls()).toHaveLength(2);
    for (const call of workers[1].calls()) {
      expect(call.method).toBe("export_pattern");
      expect(call.args).toEqual([MODEL_JSON]);
    }
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
    expect(saved).toEqual([[PDF_B64, FILE]]);
  });

  for (const [what, kind, message] of [
    ["a failure in the worker's call plumbing", "internal", WORKER_FAILED_SENTENCE],
    ["a worker that never booted", "worker", NOT_BOOTED_SENTENCE],
  ] as const) {
    it(`restarts the engine for the summary's Retry after ${what}`, async () => {
      const { client, worker, workers } = bootedClient();
      const { loader } = makeLoader(client);
      const { controller } = makeController(client);

      loader.load(MODEL_JSON);
      await settle();
      worker.respond(worker.calls()[0].id!, failure(kind, message));
      await settle();
      expect(loader.view).toEqual({ status: "failed", message: FAILED_SENTENCE });
      expect(loader.workerDown).toBe(true);

      retryPattern(targets(client, loader, controller), "summary");
      await settle();
      workers[1].bootDone();
      await settle();
      // Hand count: one restart, nothing more to the broken worker, and the
      // one failed summary sent once to the new worker.
      expect(workers).toHaveLength(2);
      expect(worker.calls()).toHaveLength(1);
      expect(workers[1].calls()).toHaveLength(1);
      expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
      workers[1].respond(workers[1].calls()[0].id!, ready());
      await settle();
      expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
      // No PDF was asked for, so the Retry made none.
      expect(controller.view).toEqual({ status: "idle", message: null });
    });
  }

  it("sends the call again to the same worker after a bridge error, with no restart", async () => {
    const { client, worker, workers } = bootedClient();
    const { loader } = makeLoader(client);
    const { controller, saved } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    worker.respond(worker.calls()[0].id!, failure("internal", BRIDGE_INTERNAL_SENTENCE));
    await settle();
    expect(controller.view).toEqual({ status: "failed", message: FAILED_SENTENCE });
    expect(controller.workerDown).toBe(false);

    retryPattern(targets(client, loader, controller), "pdf");
    await settle();
    // Hand count: no restart, so one worker, holding the failed call and the
    // Retry's call.
    expect(workers).toHaveLength(1);
    expect(worker.calls()).toHaveLength(2);
    worker.respond(worker.calls()[1].id!, ready());
    await settle();
    expect(saved).toEqual([[PDF_B64, FILE]]);
  });

  it("tells the worker's failures from the bridge's by the sentences their sources send", () => {
    // The sources still send the sentences isWorkerFailure reads, so a
    // reworded one fails here instead of quietly turning a broken worker's
    // Retry back into a resend to it.
    const bridge = readFileSync(new URL("../../../qrep/bridge.py", import.meta.url), "utf8");
    expect(bridge).toContain(`_error("internal", "${BRIDGE_INTERNAL_SENTENCE}")`);
    const workerSource = readFileSync(new URL("../engine/worker.ts", import.meta.url), "utf8");
    expect(workerSource).toContain(`: "${WORKER_FAILED_SENTENCE}"`);
    expect(workerSource).toContain(`fail("worker", "${NOT_BOOTED_SENTENCE}")`);

    expect(isWorkerFailure(new EngineError("internal", WORKER_FAILED_SENTENCE))).toBe(true);
    expect(isWorkerFailure(new EngineError("internal", "no envelope"))).toBe(true);
    expect(isWorkerFailure(new EngineError("worker", NOT_BOOTED_SENTENCE))).toBe(true);
    expect(isWorkerFailure(new EngineError("internal", BRIDGE_INTERNAL_SENTENCE))).toBe(false);
    expect(isWorkerFailure(new EngineError("value", "unknown strategy: zigzag"))).toBe(false);
    // A restart's rejection is no failure at all: the call goes again on its own.
    expect(isWorkerFailure(new EngineError("worker", "the engine was restarted"))).toBe(false);
    expect(isWorkerFailure(new Error(WORKER_FAILED_SENTENCE))).toBe(false);
  });
});

// A hand-made census for the fixture's two fabrics: 1246 blue and 1229 cream
// are the design doc's census literals; the other fields are carried through.
const CENSUS: ModelSummary = {
  name: "Double Irish Chain 75x90",
  rows: 55,
  cols: 45,
  fabric_count: 2,
  fabrics: [
    { id: "b", name: "Chain blue", color: "#9db8d9", cell_count: 1246 },
    { id: "c", name: "Background cream", color: "#f2e8d5", cell_count: 1229 },
  ],
  finished_width: 600,
  finished_height: 720,
  batting_width: 664,
  batting_height: 784,
  usable_width: 336,
};

function makeCensus(client: EngineClient) {
  const summaries: ModelSummary[] = [];
  const errors: string[] = [];
  const queue = new CensusQueue({
    validate: (json) => client.call<ModelSummary>("validate", json),
    onSummary: (summary) => summaries.push(summary),
    onError: (message) => errors.push(message),
  });
  return { queue, summaries, errors };
}

describe("CensusQueue", () => {
  it("asks again for a census a restart rejected, so Retry after a failed boot shows it", async () => {
    const { client, workers } = failedBootClient();
    const { queue, summaries, errors } = makeCensus(client);

    queue.request(MODEL_JSON);
    await settle();
    expect(workers[0].calls()).toHaveLength(0);

    client.restart();
    await settle();
    // No toast for the restart: the census is still wanted, not failed.
    expect(errors).toEqual([]);

    workers[1].bootDone();
    await settle();
    expect(workers[1].calls()).toHaveLength(1);
    expect(workers[1].calls()[0].method).toBe("validate");
    expect(workers[1].calls()[0].args).toEqual([MODEL_JSON]);
    workers[1].respond(workers[1].calls()[0].id!, { ok: true, result: CENSUS });
    await settle();
    expect(summaries).toEqual([CENSUS]);
    expect(errors).toEqual([]);
  });

  it("does not resend a replaced model's census after a restart", async () => {
    const { client, workers } = failedBootClient();
    const { queue, summaries, errors } = makeCensus(client);

    queue.request(MODEL_JSON);
    await settle();
    queue.replace();
    client.restart();
    workers[1].bootDone();
    await settle();
    expect(workers[1].calls()).toHaveLength(0);
    expect(summaries).toEqual([]);
    expect(errors).toEqual([]);
  });

  it("still reports an engine error that is not a restart", async () => {
    const { client, worker } = bootedClient();
    const { queue, summaries, errors } = makeCensus(client);
    const message = "center.cells row 3 has 44 squares, expected 45";

    queue.request(MODEL_JSON);
    await settle();
    worker.respond(worker.calls()[0].id!, { ok: false, error: { kind: "validation", message } });
    await settle();
    expect(errors).toEqual([message]);
    expect(summaries).toEqual([]);
    expect(worker.calls()).toHaveLength(1);
    // The failure stays on record for Retry, and it was the bridge's, not the worker's.
    expect(queue.failed).toBe(true);
    expect(queue.workerDown).toBe(false);
  });

  it("forgets a failed census once a newer model replaces it, so Retry sends nothing", async () => {
    const { client, worker } = bootedClient();
    const { queue } = makeCensus(client);

    queue.request(MODEL_JSON);
    await settle();
    worker.respond(worker.calls()[0].id!, failure("internal", WORKER_FAILED_SENTENCE));
    await settle();
    expect(queue.failed).toBe(true);
    expect(queue.workerDown).toBe(true);

    queue.replace();
    expect(queue.failed).toBe(false);
    expect(queue.workerDown).toBe(false);
    queue.retry();
    await settle();
    // Hand count: the one failed validate, and nothing more.
    expect(worker.calls()).toHaveLength(1);
  });
});

/** The census's answer on a fresh worker, and the summary's to anything else. */
function answer(call: Sent) {
  return call.method === "validate" ? { ok: true, result: CENSUS } : ready();
}

describe("Retry and the fabric census", () => {
  it("sends a census the broken worker failed again with the summary's Retry, on one restart", async () => {
    const { client, worker, workers } = bootedClient();
    const { queue, summaries, errors } = makeCensus(client);
    const { loader } = makeLoader(client);
    const { controller } = makeController(client);

    // As on Your pattern: the census is asked for first, then the summary.
    queue.request(MODEL_JSON);
    loader.load(MODEL_JSON);
    await settle();
    // One call at a time: the worker fails the validate, then the summary.
    worker.respond(worker.calls()[0].id!, failure("internal", WORKER_FAILED_SENTENCE));
    await settle();
    worker.respond(worker.calls()[1].id!, failure("internal", WORKER_FAILED_SENTENCE));
    await settle();
    expect(worker.calls().map((call) => call.method)).toEqual(["validate", "export_pattern"]);
    expect(queue.failed).toBe(true);
    expect(queue.workerDown).toBe(true);
    expect(loader.view).toEqual({ status: "failed", message: FAILED_SENTENCE });

    // The error line shows the summary's failure first, so its Retry is the one.
    retryPattern(targets(client, loader, controller, queue), "summary");
    await settle();
    workers[1].bootDone();
    await settle();
    // The new worker takes one call at a time: answer the first, then the second.
    for (let i = 0; i < 2; i++) {
      const call = workers[1].calls()[i];
      workers[1].respond(call.id!, answer(call));
      await settle();
    }

    // Hand count: two calls failed on the first worker, and the one Retry
    // restarted the engine once and sent each once more: two workers, the
    // first holding its two failed calls, the second one validate and one
    // export_pattern, each with the model JSON alone.
    expect(workers).toHaveLength(2);
    expect(worker.calls()).toHaveLength(2);
    expect(workers[1].calls().map((call) => call.method).sort()).toEqual([
      "export_pattern",
      "validate",
    ]);
    for (const call of workers[1].calls()) expect(call.args).toEqual([MODEL_JSON]);
    expect(summaries).toEqual([CENSUS]);
    expect(queue.failed).toBe(false);
    expect(loader.view).toEqual({ status: "ready", summary: SUMMARY });
    // The worker's failure reached the census's error report once, on the
    // first worker; the Retry added none.
    expect(errors).toEqual([WORKER_FAILED_SENTENCE]);
    // No PDF was asked for, so the Retry made none.
    expect(controller.view).toEqual({ status: "idle", message: null });
  });

  it("sends a census that failed alone again to the same worker after a bridge error, with no restart", async () => {
    const { client, worker, workers } = bootedClient();
    const { queue, summaries } = makeCensus(client);
    const { loader } = makeLoader(client);
    const { controller } = makeController(client);

    queue.request(MODEL_JSON);
    await settle();
    worker.respond(worker.calls()[0].id!, failure("internal", BRIDGE_INTERNAL_SENTENCE));
    await settle();
    expect(queue.failed).toBe(true);
    expect(queue.workerDown).toBe(false);

    retryPattern(targets(client, loader, controller, queue), "census");
    await settle();
    // Hand count: no restart, so one worker, holding the failed validate and
    // the Retry's one validate; the idle summary and PDF sent nothing.
    expect(workers).toHaveLength(1);
    expect(worker.calls()).toHaveLength(2);
    expect(worker.calls()[1].method).toBe("validate");
    expect(worker.calls()[1].args).toEqual([MODEL_JSON]);
    worker.respond(worker.calls()[1].id!, { ok: true, result: CENSUS });
    await settle();
    expect(summaries).toEqual([CENSUS]);
    expect(queue.failed).toBe(false);
  });

  it("sends a failed census again after an engine Retry", async () => {
    const { client, worker, workers } = bootedClient();
    const { queue, summaries } = makeCensus(client);
    const { loader } = makeLoader(client);
    const { controller } = makeController(client);

    queue.request(MODEL_JSON);
    await settle();
    worker.respond(worker.calls()[0].id!, failure("internal", BRIDGE_INTERNAL_SENTENCE));
    await settle();

    retryPattern(targets(client, loader, controller, queue), "engine");
    await settle();
    workers[1].bootDone();
    await settle();
    // Hand count: the engine Retry restarts once, and the failed census goes
    // once to the new worker.
    expect(workers).toHaveLength(2);
    expect(worker.calls()).toHaveLength(1);
    expect(workers[1].calls()).toHaveLength(1);
    expect(workers[1].calls()[0].method).toBe("validate");
    workers[1].respond(workers[1].calls()[0].id!, { ok: true, result: CENSUS });
    await settle();
    expect(summaries).toEqual([CENSUS]);
  });
});

describe("patternPdfName", () => {
  it("names the file from the validate summary's pattern name", () => {
    // Hand: "Double Irish Chain 75x90" lowercased is "double irish chain
    // 75x90"; each of the three spaces is one run of characters outside a-z
    // and 0-9, so each becomes one hyphen: "double-irish-chain-75x90.pdf".
    expect(
      patternPdfName({ name: "Double Irish Chain 75x90" }, { metadata: { name: "Other name" } }),
    ).toBe("double-irish-chain-75x90.pdf");
  });

  it("falls back to the model's own name without a summary", () => {
    // Hand: "Log Cabin, Lap!" lowercased is "log cabin, lap!"; the runs " ",
    // ", " and "!" each become one hyphen, giving "log-cabin-lap-", and the
    // trailing hyphen is trimmed: "log-cabin-lap.pdf".
    expect(patternPdfName(null, { metadata: { name: "Log Cabin, Lap!" } })).toBe("log-cabin-lap.pdf");
    // Hand: an empty summary name is no name, so the model's "Star" gives "star".
    expect(patternPdfName({ name: "" }, { metadata: { name: "Star" } })).toBe("star.pdf");
  });

  it("trims hyphens at both ends and names an empty pattern quilt.pdf", () => {
    // Hand: "  --Ohio Star--  " lowercased keeps its characters; the leading
    // "  --" and trailing "--  " are one run each and the inner space is one,
    // giving "-ohio-star-", trimmed to "ohio-star".
    expect(patternPdfName({ name: "  --Ohio Star--  " }, { metadata: { name: "" } })).toBe(
      "ohio-star.pdf",
    );
    // Hand: no name at all slugs to "", which slugify replaces with "quilt".
    expect(patternPdfName(null, { metadata: { name: "" } })).toBe("quilt.pdf");
  });
});
