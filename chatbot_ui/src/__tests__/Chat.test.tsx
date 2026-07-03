import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import Chat from "../components/Chat";

vi.mock("../api");

describe("Chat component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("toont welkomstbericht bij laden", () => {
    render(<Chat />);
    expect(screen.getByText(/kennisassistent/i)).toBeInTheDocument();
  });

  it("toont invoerveld", () => {
    render(<Chat />);
    expect(screen.getByPlaceholderText(/vraag/i)).toBeInTheDocument();
  });

  it("verstuurknop is uitgeschakeld bij leeg invoerveld", () => {
    render(<Chat />);
    const button = screen.getByRole("button", { name: /versturen/i });
    expect(button).toBeDisabled();
  });

  it("verstuurknop is ingeschakeld na invoer", async () => {
    render(<Chat />);
    const textarea = screen.getByPlaceholderText(/vraag/i);
    await userEvent.type(textarea, "Wat is een contract?");
    const button = screen.getByRole("button", { name: /versturen/i });
    expect(button).not.toBeDisabled();
  });

  it("versturen werkt ook zonder crypto.randomUUID (http via LAN-IP)", async () => {
    // crypto.randomUUID bestaat alleen in secure contexts — simuleer een
    // browser die de pagina via http://<ip> laadt
    const origRandomUUID = globalThis.crypto.randomUUID;
    // @ts-expect-error — bewust verwijderen voor deze test
    globalThis.crypto.randomUUID = undefined;
    try {
      vi.mocked(api.sendMessageStream).mockImplementation(async function* () {
        yield { token: "Antwoord zonder uuid" };
        yield { done: true, sources: [] };
      });

      render(<Chat />);
      const textarea = screen.getByPlaceholderText(/vraag/i);
      await userEvent.type(textarea, "Werkt dit ook via een LAN-IP?");
      await userEvent.keyboard("{Enter}");

      expect(screen.getByText("Werkt dit ook via een LAN-IP?")).toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getByText("Antwoord zonder uuid")).toBeInTheDocument();
      });
    } finally {
      globalThis.crypto.randomUUID = origRandomUUID;
    }
  });

  it("verstuurt bericht en toont antwoord", async () => {
    vi.mocked(api.sendMessageStream).mockImplementation(async function* () {
      yield { token: "Een contract is een overeenkomst." };
      yield { done: true, sources: [] };
    });

    render(<Chat />);
    const textarea = screen.getByPlaceholderText(/vraag/i);
    await userEvent.type(textarea, "Wat is een contract?");
    await userEvent.keyboard("{Enter}");

    expect(screen.getByText("Wat is een contract?")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Een contract is een overeenkomst.")).toBeInTheDocument();
    });
  });

  it("toont foutmelding bij mislukte API-aanroep", async () => {
    // biome-ignore lint/correctness/useYield: generator throws before first yield — intentional mock
    vi.mocked(api.sendMessageStream).mockImplementation(async function* () {
      throw new Error("Verbindingsfout");
    });

    render(<Chat />);
    const textarea = screen.getByPlaceholderText(/vraag/i);
    await userEvent.type(textarea, "Vraag");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText(/Verbindingsfout/i)).toBeInTheDocument();
    });
  });

  it("toont bronnen bij antwoord met sources", async () => {
    vi.mocked(api.sendMessageStream).mockImplementation(async function* () {
      yield { token: "Antwoord" };
      yield {
        done: true,
        sources: [{ file: "contract.pdf", topic_label: "Contractrecht", passage: "", page: null }],
      };
    });

    render(<Chat />);
    const textarea = screen.getByPlaceholderText(/vraag/i);
    await userEvent.type(textarea, "Vraag over bronnen");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Contractrecht")).toBeInTheDocument();
    });
  });

  it("bronlink opent in nieuw tabblad zodat de chatgeschiedenis behouden blijft", async () => {
    vi.mocked(api.sendMessageStream).mockImplementation(async function* () {
      yield { token: "Antwoord" };
      yield {
        done: true,
        sources: [{ file: "contract.pdf", topic_label: "Contractrecht", passage: "", page: null }],
      };
    });

    render(<Chat />);
    const textarea = screen.getByPlaceholderText(/vraag/i);
    await userEvent.type(textarea, "Vraag over bronnen");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      const link = screen.getByText("Contractrecht").closest("a");
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
      expect(link).not.toHaveAttribute("download");
    });
  });
});
