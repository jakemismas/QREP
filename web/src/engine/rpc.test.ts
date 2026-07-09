/**
 * RPC layer tests (S2, issue #42): request/response correlation, error
 * envelope propagation, single in-flight queue with busy states, and
 * terminate-and-reboot safety, all against a scripted fake worker.
 */
import { describe, expect, it } from "vitest";
import { EngineClient, EngineError, type EngineStatus, type WorkerLike } from "./rpc";

interface Sent {
  type: string;
  id?: number;
  method?: string;
  args?: unknown[];
}

class FakeWorker implements WorkerLike {
  sent: Sent[] = [];
  terminated = false;
  onmessage: ((event: MessageEvent) => void) | null = null;

  postMessage(message: unknown): void {
    this.sent.push(message as Sent);
  }

  terminate(): void {
    this.terminated = true;
  }

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

function makeClient(): { client: EngineClient; workers: FakeWorker[] } {
  const workers: FakeWorker[] = [];
  const client = new EngineClient(() => {
    const worker = new FakeWorker();
    workers.push(worker);
    return worker;
  });
  return { client, workers };
}

describe("EngineClient", () => {
  it("correlates out-of-order responses by request id", async () => {
    const { client, workers } = makeClient();
    client.start();
    const worker = workers[0];
    worker.bootDone();

    const first = client.call<string>("validate", "{model-a}");
    const second = client.call<string>("validate", "{model-b}");
    // Single in-flight: only the first call is posted until it resolves.
    expect(worker.calls()).toHaveLength(1);
    const firstId = worker.calls()[0].id!;
    worker.respond(firstId, { ok: true, result: "A" });
    await expect(first).resolves.toBe("A");

    // Now the queued second call goes out; respond and check it got its own
    // payload, not the first one's.
    await Promise.resolve();
    expect(worker.calls()).toHaveLength(2);
    const secondId = worker.calls()[1].id!;
    expect(secondId).not.toBe(firstId);
    worker.respond(secondId, { ok: true, result: "B" });
    await expect(second).resolves.toBe("B");
  });

  it("rejects with EngineError carrying the envelope kind", async () => {
    const { client, workers } = makeClient();
    client.start();
    workers[0].bootDone();
    const call = client.call("validate", "{broken");
    await Promise.resolve();
    const id = workers[0].calls()[0].id!;
    workers[0].respond(id, {
      ok: false,
      error: { kind: "validation", message: "model failed validation: palette" },
    });
    const error = await call.catch((e) => e);
    expect(error).toBeInstanceOf(EngineError);
    expect(error.kind).toBe("validation");
    expect(error.message).toContain("palette");
  });

  it("tracks status booting -> ready -> busy -> ready", async () => {
    const { client, workers } = makeClient();
    const phases: string[] = [];
    client.onStatus((status: EngineStatus) => phases.push(status.phase));
    client.start();
    expect(phases.at(-1)).toBe("booting");
    workers[0].emit({ type: "boot-progress", step: "Loading engine packages" });
    expect(phases.at(-1)).toBe("booting");
    workers[0].bootDone();
    expect(phases.at(-1)).toBe("ready");
    const call = client.call("plan", "{}", "strip");
    expect(phases.at(-1)).toBe("busy");
    await Promise.resolve();
    workers[0].respond(workers[0].calls()[0].id!, { ok: true, result: {} });
    await call;
    expect(phases.at(-1)).toBe("ready");
  });

  it("boot failure surfaces failed status and retry reboots a fresh worker", async () => {
    const { client, workers } = makeClient();
    const phases: string[] = [];
    client.onStatus((status: EngineStatus) => phases.push(status.phase));
    client.start();
    workers[0].emit({ type: "boot-failed", message: "wheel fetch failed" });
    expect(phases.at(-1)).toBe("failed");

    client.restart();
    expect(workers[0].terminated).toBe(true);
    expect(workers).toHaveLength(2);
    expect(phases.at(-1)).toBe("booting");
    workers[1].bootDone();
    expect(phases.at(-1)).toBe("ready");
    const call = client.call<string>("validate", "{}");
    await Promise.resolve();
    workers[1].respond(workers[1].calls()[0].id!, { ok: true, result: "fine" });
    await expect(call).resolves.toBe("fine");
  });

  it("restart rejects in-flight and queued calls with kind worker", async () => {
    const { client, workers } = makeClient();
    client.start();
    workers[0].bootDone();
    const inFlight = client.call("plan", "{}", "strip");
    const queued = client.call("validate", "{}");
    client.restart();
    const errors = await Promise.all([inFlight.catch((e) => e), queued.catch((e) => e)]);
    for (const error of errors) {
      expect(error).toBeInstanceOf(EngineError);
      expect(error.kind).toBe("worker");
    }
    // The replacement worker is functional after boot.
    workers[1].bootDone();
    const call = client.call<string>("validate", "{}");
    await Promise.resolve();
    workers[1].respond(workers[1].calls()[0].id!, { ok: true, result: "ok" });
    await expect(call).resolves.toBe("ok");
  });

  it("streams vision state and prefetch posts load-vision (S6)", () => {
    const { client, workers } = makeClient();
    const states: string[] = [];
    client.onVision((state) => states.push(state));
    client.start();
    workers[0].bootDone();
    expect(states.at(-1)).toBe("cold");

    client.prefetchVision();
    expect(workers[0].sent.some((m) => m.type === "load-vision")).toBe(true);
    workers[0].emit({ type: "vision-progress" });
    expect(states.at(-1)).toBe("loading");
    workers[0].emit({ type: "vision-ready" });
    expect(states.at(-1)).toBe("ready");
  });

  it("vision failure surfaces failed state and restart resets to cold", () => {
    const { client, workers } = makeClient();
    const states: string[] = [];
    client.onVision((state) => states.push(state));
    client.start();
    workers[0].bootDone();
    client.prefetchVision();
    workers[0].emit({ type: "vision-failed", message: "network" });
    expect(states.at(-1)).toBe("failed");
    client.restart();
    expect(states.at(-1)).toBe("cold");
  });

  it("calls made before boot completes queue and run after ready", async () => {
    const { client, workers } = makeClient();
    client.start();
    const early = client.call<string>("validate", "{}");
    expect(workers[0].calls()).toHaveLength(0);
    workers[0].bootDone();
    await Promise.resolve();
    expect(workers[0].calls()).toHaveLength(1);
    workers[0].respond(workers[0].calls()[0].id!, { ok: true, result: "early" });
    await expect(early).resolves.toBe("early");
  });
});
