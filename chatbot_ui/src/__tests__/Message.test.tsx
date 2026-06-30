import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Message, MessageActions, MessageContent } from "../components/prompt-kit/message";

describe("Message components", () => {
  it("rendert Message met content", () => {
    render(<Message>Testbericht</Message>);
    expect(screen.getByText("Testbericht")).toBeInTheDocument();
  });

  it("rendert MessageContent met kinderen", () => {
    render(<MessageContent>Antwoord van de assistent</MessageContent>);
    expect(screen.getByText("Antwoord van de assistent")).toBeInTheDocument();
  });

  it("MessageContent accepteert className", () => {
    const { container } = render(<MessageContent className="mijn-klasse">tekst</MessageContent>);
    expect(container.querySelector(".mijn-klasse")).toBeTruthy();
  });

  it("rendert MessageActions", () => {
    render(<MessageActions>Acties</MessageActions>);
    expect(screen.getByText("Acties")).toBeInTheDocument();
  });

  it("Message accepteert className", () => {
    const { container } = render(<Message className="bericht-klasse">tekst</Message>);
    expect(container.querySelector(".bericht-klasse")).toBeTruthy();
  });
});
