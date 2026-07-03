import { beforeEach, describe, expect, it, vi } from "vitest";
import { getSettings, sendMessage, sendMessageStream, setProvider } from "../api";

function makeSSEStream(...events: object[]) {
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function mockFetch(stream: ReadableStream | null, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok, status, statusText: ok ? "OK" : "Error", body: stream }),
  );
}

describe("sendMessageStream", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("yield tokens en done event", async () => {
    mockFetch(makeSSEStream({ token: "Hallo" }, { done: true, sources: [] }));

    const chunks = [];
    for await (const chunk of sendMessageStream("test", [])) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual([{ token: "Hallo" }, { done: true, sources: [] }]);
  });

  it("gooit fout bij niet-ok response", async () => {
    mockFetch(null, false, 500);

    await expect(async () => {
      for await (const _ of sendMessageStream("test", [])) {
        // noop
      }
    }).rejects.toThrow("API fout: 500");
  });

  it("honoreert AbortSignal", async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(Object.assign(new Error("aborted"), { name: "AbortError" })),
    );

    controller.abort();
    await expect(async () => {
      for await (const _ of sendMessageStream("test", [], controller.signal)) {
        // noop
      }
    }).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("sendMessage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("assembleert volledig antwoord uit stream", async () => {
    mockFetch(
      makeSSEStream(
        { token: "Hallo " },
        { token: "wereld" },
        { done: true, sources: [{ file: "test.pdf", topic_label: "Test", passage: "", page: 1 }] },
      ),
    );

    const result = await sendMessage("test", []);
    expect(result.answer).toBe("Hallo wereld");
    expect(result.sources).toHaveLength(1);
    expect(result.sources[0].file).toBe("test.pdf");
    expect(result.sources[0].page).toBe(1);
  });

  it("geeft lege sources bij stream zonder done event", async () => {
    mockFetch(makeSSEStream({ token: "Antwoord" }));

    const result = await sendMessage("test", []);
    expect(result.answer).toBe("Antwoord");
    expect(result.sources).toEqual([]);
  });
});

describe("getSettings", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("geeft de settings terug", async () => {
    const settings = {
      provider: "ollama",
      claude_available: true,
      claude_model: "claude-sonnet-5",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => settings }));

    expect(await getSettings()).toEqual(settings);
  });

  it("gooit fout bij niet-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, statusText: "Error" }),
    );

    await expect(getSettings()).rejects.toThrow("API fout: 500");
  });
});

describe("setProvider", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("POST de gekozen provider", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    await setProvider("claude");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/settings"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ provider: "claude" }),
      }),
    );
  });

  it("gooit fout bij niet-ok response (bijv. geen API-key)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 400, statusText: "Bad Request" }),
    );

    await expect(setProvider("claude")).rejects.toThrow("API fout: 400");
  });
});
