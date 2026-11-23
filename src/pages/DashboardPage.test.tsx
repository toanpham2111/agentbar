import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import { monitorApi } from "../lib/api";
import { providerFixture, summaryFixture } from "../test/fixtures";
import { DashboardPage } from "./DashboardPage";

vi.mock("../lib/api", () => ({
  monitorApi: {
    getProviders: vi.fn(),
    getUsageSummary: vi.fn(),
    refreshAll: vi.fn(),
    refreshProvider: vi.fn(),
  },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><DashboardPage /></QueryClientProvider>);
}

describe("DashboardPage", () => {
  it("renders verified provider data and preserves unavailable cost", async () => {
    vi.mocked(monitorApi.getProviders).mockResolvedValue([providerFixture]);
    vi.mocked(monitorApi.getUsageSummary).mockResolvedValue(summaryFixture);
    renderPage();
    expect(await screen.findByText("OpenAI Codex")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("Unsupported by provider")).toBeInTheDocument();
  });

  it("shows a recoverable error when the desktop backend fails", async () => {
    vi.mocked(monitorApi.getProviders).mockRejectedValue(new Error("backend offline"));
    vi.mocked(monitorApi.getUsageSummary).mockRejectedValue(new Error("backend offline"));
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("backend offline");
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });
});
