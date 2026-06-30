import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  PromptInput,
  PromptInputActions,
  PromptInputTextarea,
} from "../components/prompt-kit/prompt-input";

describe("PromptInput components", () => {
  it("rendert textarea met placeholder", () => {
    render(
      <PromptInput value="" onValueChange={() => {}}>
        <PromptInputTextarea placeholder="Typ hier..." />
      </PromptInput>,
    );
    expect(screen.getByPlaceholderText("Typ hier...")).toBeInTheDocument();
  });

  it("roept onValueChange aan bij typen", async () => {
    const onChange = vi.fn();
    render(
      <PromptInput value="" onValueChange={onChange}>
        <PromptInputTextarea placeholder="Typ..." />
      </PromptInput>,
    );
    const textarea = screen.getByPlaceholderText("Typ...");
    await userEvent.type(textarea, "hallo");
    expect(onChange).toHaveBeenCalled();
  });

  it("roept onSubmit aan bij Enter", async () => {
    const onSubmit = vi.fn();
    render(
      <PromptInput value="test" onValueChange={() => {}} onSubmit={onSubmit}>
        <PromptInputTextarea placeholder="Typ..." />
      </PromptInput>,
    );
    const textarea = screen.getByPlaceholderText("Typ...");
    await userEvent.type(textarea, "{Enter}");
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("verstuurt niet bij Shift+Enter", async () => {
    const onSubmit = vi.fn();
    render(
      <PromptInput value="test" onValueChange={() => {}} onSubmit={onSubmit}>
        <PromptInputTextarea placeholder="Typ..." />
      </PromptInput>,
    );
    const textarea = screen.getByPlaceholderText("Typ...");
    await userEvent.type(textarea, "{Shift>}{Enter}{/Shift}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("textarea is uitgeschakeld als disabled=true", () => {
    render(
      <PromptInput value="" onValueChange={() => {}} disabled>
        <PromptInputTextarea placeholder="Typ..." />
      </PromptInput>,
    );
    expect(screen.getByPlaceholderText("Typ...")).toBeDisabled();
  });

  it("rendert PromptInputActions met kinderen", () => {
    render(
      <PromptInput value="" onValueChange={() => {}}>
        <PromptInputActions>
          <button type="button">Actie</button>
        </PromptInputActions>
      </PromptInput>,
    );
    expect(screen.getByRole("button", { name: "Actie" })).toBeInTheDocument();
  });
});
