/**
 * Your pattern's engine calls (C2a, issue #96): the PDF controller and the
 * summary loader, driven through EngineClient by a scripted fake worker
 * (the FakeWorker shape from engine/rpc.test.ts). No DOM: the controller
 * hands the PDF to a save callback, which the screen wires to a file save.
 */
import { describe, expect, it } from "vitest";
import { EngineClient, type WorkerLike } from "../engine/rpc";
import { base64ToArrayBuffer, patternFileName } from "../state/pattern";
import {
  PATTERN_FAILED,
  PatternPdfController,
  PatternSummaryLoader,
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

function bootedClient(): { client: EngineClient; worker: FakeWorker } {
  const workers: FakeWorker[] = [];
  const client = new EngineClient(() => {
    const worker = new FakeWorker();
    workers.push(worker);
    return worker;
  });
  client.start();
  workers[0].bootDone();
  return { client, worker: workers[0] };
}

// Promise callbacks from the client and the controller run as microtasks; a
// macrotask lets every one of them settle first.
const settle = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

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
    expect(controller.view).toEqual({ status: "failed", message: PATTERN_FAILED });
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

  it("shows a refused outcome's reason, which is written for people", async () => {
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
    expect(controller.view).toEqual({ status: "failed", message });
    expect(saved).toEqual([]);
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
    expect(controller.view).toEqual({ status: "failed", message: PATTERN_FAILED });
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

  it("names the file from the pattern name in kebab case and saves the decoded PDF", async () => {
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
    expect(loader.view).toEqual({ status: "failed", message: PATTERN_FAILED });

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
