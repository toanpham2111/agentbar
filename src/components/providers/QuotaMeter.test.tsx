import { render, screen } from "@testing-library/react";
import { QuotaMeter } from "./QuotaMeter";

describe("QuotaMeter", () => {
  it("renders an explicit unavailable state instead of a fake zero", () => {
    render(<QuotaMeter quota={{ id: "weekly", label: "Weekly", usedPercent: null, remainingPercent: null, resetsAt: null, source: "unavailable", reliable: false }} />);
    expect(screen.getByText("Quota unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("clamps invalid provider percentages at the display boundary", () => {
    render(<QuotaMeter quota={{ id: "five-hour", label: "5-hour", usedPercent: 140, remainingPercent: 0, resetsAt: null, source: "official_api", reliable: true }} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText("100% used")).toBeInTheDocument();
  });
});
