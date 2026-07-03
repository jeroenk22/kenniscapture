import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";
import ProviderToggle from "../components/ProviderToggle";

vi.mock("../api");

describe("ProviderToggle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("toont de actieve provider (ollama)", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      provider: "ollama",
      claude_available: true,
      claude_model: "claude-sonnet-5",
    });

    render(<ProviderToggle />);
    expect(await screen.findByText(/Ollama \(lokaal\)/)).toBeInTheDocument();
  });

  it("toont cloud-waarschuwing als Claude actief is", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      provider: "claude",
      claude_available: true,
      claude_model: "claude-sonnet-5",
    });

    render(<ProviderToggle />);
    expect(await screen.findByText(/Claude \(cloud\)/)).toBeInTheDocument();
    expect(screen.getByText(/Data gaat naar Anthropic/)).toBeInTheDocument();
  });

  it("is uitgeschakeld als Claude niet beschikbaar is", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      provider: "ollama",
      claude_available: false,
      claude_model: "claude-sonnet-5",
    });

    render(<ProviderToggle />);
    const knop = await screen.findByRole("button");
    expect(knop).toBeDisabled();
    expect(knop).toHaveAttribute("title", expect.stringContaining("ANTHROPIC_API_KEY"));
  });

  it("switcht naar Claude via de API", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      provider: "ollama",
      claude_available: true,
      claude_model: "claude-sonnet-5",
    });
    vi.mocked(api.setProvider).mockResolvedValue();

    render(<ProviderToggle />);
    const knop = await screen.findByRole("button");
    await userEvent.click(knop);

    expect(api.setProvider).toHaveBeenCalledWith("claude");
    await waitFor(() => {
      expect(screen.getByText(/Claude \(cloud\)/)).toBeInTheDocument();
    });
  });

  it("behoudt de huidige stand als de switch mislukt", async () => {
    vi.mocked(api.getSettings).mockResolvedValue({
      provider: "ollama",
      claude_available: true,
      claude_model: "claude-sonnet-5",
    });
    vi.mocked(api.setProvider).mockRejectedValue(new Error("400"));

    render(<ProviderToggle />);
    const knop = await screen.findByRole("button");
    await userEvent.click(knop);

    await waitFor(() => {
      expect(screen.getByText(/Ollama \(lokaal\)/)).toBeInTheDocument();
    });
  });

  it("rendert niets als de backend niet bereikbaar is", async () => {
    vi.mocked(api.getSettings).mockRejectedValue(new Error("offline"));

    const { container } = render(<ProviderToggle />);
    await waitFor(() => {
      expect(container).toBeEmptyDOMElement();
    });
  });

  it("ververst de stand periodiek — switch uit Streamlit wordt vanzelf zichtbaar", async () => {
    vi.useFakeTimers();
    try {
      vi.mocked(api.getSettings)
        .mockResolvedValueOnce({
          provider: "ollama",
          claude_available: true,
          claude_model: "claude-sonnet-5",
        })
        .mockResolvedValue({
          provider: "claude",
          claude_available: true,
          claude_model: "claude-sonnet-5",
        });

      render(<ProviderToggle />);
      await act(async () => {
        await Promise.resolve();
      });
      expect(screen.getByText(/Ollama \(lokaal\)/)).toBeInTheDocument();

      // Na het poll-interval toont de toggle de nieuwe stand zonder F5
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      expect(screen.getByText(/Claude \(cloud\)/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
