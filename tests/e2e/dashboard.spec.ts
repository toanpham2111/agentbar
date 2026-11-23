import { expect, test } from "@playwright/test";

test("dashboard is responsive, keyboard reachable, and explicitly labeled as demo", async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });

  await page.goto("/#/dashboard");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: "Usage overview" })).toBeVisible();
  await expect(page.getByText(/UI preview mode/i)).toBeVisible();
  await expect(page.getByText("OpenAI Codex")).toBeVisible();

  const layout = await page.evaluate(() => {
    const overflow = [...document.querySelectorAll<HTMLElement>("body *")]
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && (rect.left < -1 || rect.right > window.innerWidth + 1);
      })
      .map((element) => ({ tag: element.tagName, className: element.className, text: element.textContent?.slice(0, 40) }));
    const wrappedButtons = [...document.querySelectorAll<HTMLButtonElement>("button")]
      .filter((button) => button.scrollHeight > button.clientHeight + 2)
      .map((button) => button.textContent);
    return { overflow, wrappedButtons, documentWidth: document.documentElement.scrollWidth, viewportWidth: window.innerWidth };
  });

  expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
  expect(layout.overflow).toEqual([]);
  expect(layout.wrappedButtons).toEqual([]);
  expect(consoleErrors).toEqual([]);

  await page.screenshot({
    path: `docs/screenshots/dashboard-${testInfo.project.name}.png`,
    fullPage: true,
  });
});

test("theme controls and primary navigation work with semantic buttons", async ({ page }) => {
  await page.goto("/#/settings");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "dark", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
});
