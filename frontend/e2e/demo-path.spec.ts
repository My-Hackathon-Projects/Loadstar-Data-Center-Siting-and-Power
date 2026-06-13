import { expect, test } from "@playwright/test";

test("demo path: intro skip → dashboard → fred → tech → thanks, no console errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));

  // The journey loads on /. Awaiting is gesture-gated, so the skip control is
  // available immediately and jumps straight to the dashboard.
  await page.goto("/");
  await expect(page.getByRole("button", { name: "skip to app" })).toBeVisible();
  await page.getByRole("button", { name: "skip to app" }).click();
  await expect(page).toHaveURL(/\/app$/);

  // The dashboard renders from real API data: ranked sites and stat cards.
  await expect(page.getByText("specifications").first()).toBeVisible();
  await expect(page.getByText("Lulea / Boden").first()).toBeVisible();
  await expect(page.getByText("candidates")).toBeVisible();

  // Fred runs a real agent-driven search and the dashboard reacts.
  await page.getByPlaceholder("ask fred to find sites").fill("cheapest site in Sweden");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Found \d+ candidate/)).toBeVisible();

  // Behind the Tech renders, including the architecture section.
  await page.goto("/tech");
  await expect(
    page.getByRole("heading", { name: /How Loadstar finds/ }),
  ).toBeVisible();
  await expect(page.getByText("the architecture")).toBeVisible();

  // The outro renders.
  await page.goto("/thanks");
  await expect(page.getByText("and thank you, Fred.")).toBeVisible();

  expect(errors).toEqual([]);
});
