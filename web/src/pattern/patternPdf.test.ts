/**
 * Your pattern's engine calls (C2a, issue #96): the PDF controller, the
 * summary loader and the census queue, driven through EngineClient by a
 * scripted fake worker (the FakeWorker shape from engine/rpc.test.ts). No
 * DOM: the controller hands the PDF to a save callback, which the screen
 * wires to a file save.
 */
import { describe, expect, it } from "vitest";
import { EngineClient, type WorkerLike } from "../engine/rpc";
import type { ModelSummary } from "../model/types";
import { CensusQueue } from "../state/model";
import { base64ToArrayBuffer, patternFileName, patternPdfName } from "../state/pattern";
import {
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

/** A client whose first boot failed, as when the engine's files do not load;
 * client.restart() is what the screen's Retry runs (engine.retry()). */
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

  it("sends a waiting pattern again after a restart, so one Retry saves it", async () => {
    const { client, workers } = failedBootClient();
    const { controller, saved, views } = makeController(client);

    void controller.start(MODEL_JSON, FILE);
    await settle();
    expect(controller.view.status).toBe("busy");
    // The boot failed, so nothing reached the worker.
    expect(workers[0].calls()).toHaveLength(0);

    client.restart();
    void controller.resend();
    await settle();
    // The restart rejected the first call; its outcome is dropped, so the
    // pattern still reads as being made, never as failed.
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

  it("resends nothing unless a pattern is being made", async () => {
    const { client, worker } = bootedClient();
    const { controller, saved } = makeController(client);

    void controller.resend();
    void controller.start(MODEL_JSON, FILE);
    await settle();
    worker.respond(worker.calls()[0].id!, ready());
    await settle();
    void controller.resend();
    await settle();
    expect(worker.calls()).toHaveLength(1);
    expect(saved).toEqual([[PDF_B64, FILE]]);
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

  it("loads a summary a restart rejected on retry, never showing a failure", async () => {
    const { client, workers } = failedBootClient();
    const { loader, views } = makeLoader(client);

    loader.load(MODEL_JSON);
    await settle();
    client.restart();
    loader.retry();
    await settle();
    expect(loader.view).toEqual({ status: "loading" });
    expect(views.map((view) => view.status)).not.toContain("failed");

    workers[1].bootDone();
    await settle();
    expect(workers[1].calls()).toHaveLength(1);
    workers[1].respond(workers[1].calls()[0].id!, ready());
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
