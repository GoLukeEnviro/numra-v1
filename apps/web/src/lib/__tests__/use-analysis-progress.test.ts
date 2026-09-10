import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAnalysisProgress } from "@/lib/use-analysis-progress";
import { api, ApiError } from "@/api/client";
import {
  analysisJob,
  relationshipAnalysisComplete,
  relationshipAnalysisPending,
} from "@/fixtures/analysis";

vi.mock("@/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/api/client")>("@/api/client");
  return {
    ...actual,
    api: {
      workspaces: {
        relationshipAnalysis: { getLatest: vi.fn(), get: vi.fn(), create: vi.fn() },
        shadowDynamics: { getLatest: vi.fn(), get: vi.fn(), create: vi.fn() },
      },
      analysisJobs: { get: vi.fn() },
    },
  };
});

const relApi = api.workspaces.relationshipAnalysis as unknown as {
  getLatest: ReturnType<typeof vi.fn>;
  get: ReturnType<typeof vi.fn>;
  create: ReturnType<typeof vi.fn>;
};
const jobsApi = api.analysisJobs as unknown as { get: ReturnType<typeof vi.fn> };

const notFound = () => new ApiError("Not found.", "NOT_FOUND", 404);

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

function render() {
  return renderHook(() => useAnalysisProgress("workspace-1", "relationship"));
}

beforeEach(() => {
  vi.useFakeTimers();
  relApi.getLatest.mockReset();
  relApi.get.mockReset();
  relApi.create.mockReset();
  jobsApi.get.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useAnalysisProgress", () => {
  it("maps a 404 latest to the empty phase", async () => {
    relApi.getLatest.mockRejectedValue(notFound());
    const { result } = render();
    await flush();
    expect(result.current.phase).toBe("empty");
  });

  it("goes empty → pending → polls QUEUED/GENERATING → COMPLETE → re-reads by id → complete", async () => {
    relApi.getLatest.mockRejectedValue(notFound());
    relApi.create.mockResolvedValue(relationshipAnalysisPending);
    relApi.get.mockResolvedValue(relationshipAnalysisComplete);
    jobsApi.get
      .mockResolvedValueOnce(analysisJob({ status: "QUEUED", progress: 10 }))
      .mockResolvedValueOnce(analysisJob({ status: "GENERATING", progress: 80 }))
      .mockResolvedValueOnce(analysisJob({ status: "COMPLETE", progress: 100 }));

    const { result } = render();
    await flush();
    expect(result.current.phase).toBe("empty");

    act(() => result.current.launch());
    await flush(); // create resolves + first poll (QUEUED)
    expect(result.current.phase).toBe("pending");
    if (result.current.phase === "pending") expect(result.current.job?.status).toBe("QUEUED");

    await tick(2500); // GENERATING 80
    if (result.current.phase === "pending") expect(result.current.job?.progress).toBe(80);

    await tick(2500); // COMPLETE → by-id → complete
    expect(result.current.phase).toBe("complete");
    expect(relApi.get).toHaveBeenCalledWith("workspace-1", "rel-analysis-1");
  });

  it("surfaces a FAILED job as the failed phase with the verbatim error_code", async () => {
    relApi.getLatest.mockRejectedValue(notFound());
    relApi.create.mockResolvedValue(relationshipAnalysisPending);
    relApi.get.mockResolvedValue({ ...relationshipAnalysisPending, status: "FAILED" });
    jobsApi.get.mockResolvedValue(
      analysisJob({ status: "FAILED", progress: 40, error_code: "PROVIDER_TIMEOUT" }),
    );

    const { result } = render();
    await flush();
    act(() => result.current.launch());
    await flush();
    expect(result.current.phase).toBe("failed");
    if (result.current.phase === "failed") {
      expect(result.current.job?.error_code).toBe("PROVIDER_TIMEOUT");
    }
  });

  it("gives up to the error phase only after 4 consecutive poll failures", async () => {
    relApi.getLatest.mockRejectedValue(notFound());
    relApi.create.mockResolvedValue(relationshipAnalysisPending);
    jobsApi.get.mockRejectedValue(new Error("boom"));

    const { result } = render();
    await flush();
    act(() => result.current.launch());
    await flush(); // failure 1
    expect(result.current.phase).toBe("pending");
    await tick(2500); // 2
    await tick(2500); // 3
    expect(result.current.phase).toBe("pending");
    await tick(2500); // 4
    expect(result.current.phase).toBe("error");
  });

  it.each(["CONSENT_NOT_GRANTED", "RELATIONSHIP_TYPE_NOT_SET"] as const)(
    "maps a %s from the launch POST to the phaseDisabled phase",
    async (code) => {
      relApi.getLatest.mockRejectedValue(notFound());
      relApi.create.mockRejectedValue(new ApiError("nope", code, 409));

      const { result } = render();
      await flush();
      act(() => result.current.launch());
      await flush();
      expect(result.current.phase).toBe("phaseDisabled");
      if (result.current.phase === "phaseDisabled") expect(result.current.error.code).toBe(code);
    },
  );

  it("keeps the Idempotency-Key after a network/5xx create failure so a retry re-hits the same job", async () => {
    relApi.getLatest.mockRejectedValue(notFound());
    relApi.create
      .mockRejectedValueOnce(new ApiError("transient", "UNKNOWN_ERROR", 500))
      .mockResolvedValueOnce(relationshipAnalysisPending);
    jobsApi.get.mockResolvedValue(analysisJob({ status: "GENERATING", progress: 80 }));

    const { result } = render();
    await flush();

    act(() => result.current.launch());
    await flush();
    expect(result.current.phase).toBe("error");
    const firstKey = relApi.create.mock.calls[0]?.[1];

    act(() => result.current.launch());
    await flush();
    const secondKey = relApi.create.mock.calls[1]?.[1];

    expect(typeof firstKey).toBe("string");
    expect(secondKey).toBe(firstKey);
  });

  it("resets the Idempotency-Key after a phase-gate create failure so a retry is a fresh attempt", async () => {
    relApi.getLatest.mockRejectedValue(notFound());
    relApi.create
      .mockRejectedValueOnce(new ApiError("nope", "CONSENT_NOT_GRANTED", 403))
      .mockResolvedValueOnce(relationshipAnalysisPending);
    jobsApi.get.mockResolvedValue(analysisJob({ status: "GENERATING", progress: 80 }));

    const { result } = render();
    await flush();

    act(() => result.current.launch());
    await flush();
    expect(result.current.phase).toBe("phaseDisabled");
    const firstKey = relApi.create.mock.calls[0]?.[1];

    act(() => result.current.launch());
    await flush();
    const secondKey = relApi.create.mock.calls[1]?.[1];

    expect(typeof firstKey).toBe("string");
    expect(typeof secondKey).toBe("string");
    expect(secondKey).not.toBe(firstKey);
  });

  it("keeps polling after reload(): a stale run cannot clear the new run's timer", async () => {
    relApi.getLatest.mockResolvedValue(relationshipAnalysisPending);
    relApi.get.mockResolvedValue(relationshipAnalysisComplete);
    jobsApi.get
      .mockResolvedValueOnce(analysisJob({ status: "GENERATING", progress: 20 }))
      .mockResolvedValueOnce(analysisJob({ status: "GENERATING", progress: 40 }))
      .mockResolvedValue(analysisJob({ status: "COMPLETE", progress: 100 }));

    const { result } = render();
    await flush(); // initial latest -> pending -> first poll (GENERATING 20)
    expect(result.current.phase).toBe("pending");

    act(() => result.current.reload());
    await flush(); // effect re-runs; old closures must not clobber the new timer

    await tick(2500);
    await tick(2500);
    expect(result.current.phase).toBe("complete");
  });
});
