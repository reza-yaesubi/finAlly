import React from "react";
import { render, container } from "@testing-library/react";
import "@testing-library/jest-dom";
import Sparkline from "@/components/Sparkline";

describe("Sparkline", () => {
  it("renders an SVG", () => {
    const { container } = render(<Sparkline data={[100, 101, 102]} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders a flat line when data has only one point", () => {
    const { container } = render(<Sparkline data={[100]} />);
    const line = container.querySelector("line");
    expect(line).toBeInTheDocument();
  });

  it("renders polyline for multiple data points", () => {
    const { container } = render(
      <Sparkline data={[100, 101, 102, 100, 99]} />
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toBeInTheDocument();
  });

  it("uses provided color", () => {
    const { container } = render(
      <Sparkline data={[100, 101]} color="#ff0000" />
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toHaveAttribute("stroke", "#ff0000");
  });
});
