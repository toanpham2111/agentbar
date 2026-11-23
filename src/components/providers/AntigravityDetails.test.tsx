import { render, screen } from "@testing-library/react";
import type { ProviderSnapshot } from "../../types/usage";
import { AntigravityDetails } from "./AntigravityDetails";

const baseProvider: ProviderSnapshot = {
  providerId: "antigravity",
  displayName: "Google Antigravity",
  installed: true,
  version: null,
  accountId: null,
  connection: "partially_supported",
  quotaWindows: [],
  tokens: null,
  cost: { amountUsd: null, kind: "unavailable", pricingVersion: null },
  dataSourceLabel: "Installation detection only",
  lastUpdated: null,
  stale: false,
  message: null,
};

describe("AntigravityDetails", () => {
  it("shows detected installation without inventing usage values", () => {
    render(<AntigravityDetails provider={baseProvider} />);

    expect(screen.getAllByText("Detected")).toHaveLength(2);
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
    expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
  });

  it("shows the not-installed boundary", () => {
    render(<AntigravityDetails provider={{ ...baseProvider, installed: false, connection: "not_installed" }} />);

    expect(screen.getAllByText("Not detected")).toHaveLength(2);
  });

  it("states the privacy boundary when provider telemetry is unsupported", () => {
    render(<AntigravityDetails provider={{ ...baseProvider, dataSourceLabel: "Unavailable" }} />);

    expect(screen.getByText(/Private RPC ports/)).toBeInTheDocument();
    expect(screen.getByText("Source: Unavailable")).toBeInTheDocument();
  });
});
