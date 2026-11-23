import { formatCost, formatTimestamp, formatTokens } from "./format";

describe("format helpers", () => {
  it("keeps unknown values distinct from zero", () => {
    expect(formatTokens(null)).toBe("Unavailable");
    expect(formatCost(null)).toBe("Unavailable");
    expect(formatTokens(0)).toBe("0");
  });

  it("handles invalid timestamps without throwing", () => {
    expect(formatTimestamp("not-a-date")).toBe("Unavailable");
    expect(formatTimestamp(null)).toBe("Never");
  });
});
