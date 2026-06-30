import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Loader } from "../components/prompt-kit/loader";

describe("Loader component", () => {
  it("toont dots variant standaard", () => {
    render(<Loader />);
    expect(screen.getByText(/laden/i)).toBeInTheDocument();
  });

  it("toont typing variant", () => {
    render(<Loader variant="typing" />);
    expect(screen.getByText(/typen/i)).toBeInTheDocument();
  });

  it("toont circular variant", () => {
    render(<Loader variant="circular" />);
    expect(screen.getByText(/laden/i)).toBeInTheDocument();
  });

  it("accepteert size prop sm", () => {
    const { container } = render(<Loader size="sm" />);
    expect(container.firstChild).toBeTruthy();
  });

  it("accepteert size prop lg", () => {
    const { container } = render(<Loader size="lg" />);
    expect(container.firstChild).toBeTruthy();
  });

  it("accepteert className prop", () => {
    const { container } = render(<Loader className="test-class" />);
    expect(container.querySelector(".test-class")).toBeTruthy();
  });
});
