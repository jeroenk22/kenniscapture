import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Chat from "../components/Chat";

describe("Chat component", () => {
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
    const button = screen.getByRole("button", { name: /verstuur/i });
    expect(button).toBeDisabled();
  });
});
