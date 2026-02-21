// import { test, expect } from "@playwright/test"

// test.describe("Note Taking App", () => {
//   test.beforeEach(async ({ page }) => {
//     await page.goto("/")
//     await page.evaluate(() => localStorage.clear())
//     await page.reload()
//   })

//   test("has title and create form visible", async ({ page }) => {
//     await expect(
//       page.getByRole("heading", { name: "Note Taking App" }),
//     ).toBeVisible()
//     await expect(
//       page.getByRole("heading", { name: /Create New Note/ }),
//     ).toBeVisible()
//     await expect(
//       page.getByRole("button", { name: "Create Note" }),
//     ).toBeVisible()
//   })

//   test("can create a note and see it in the sidebar", async ({ page }) => {
//     await page.getByLabel("Title").fill("My first note")
//     await page.getByLabel("Body").fill("Some body text")
//     await page.getByLabel(/Tags/).fill("demo, e2e")
//     await page.getByRole("button", { name: "Create Note" }).click()

//     await expect(page.getByRole("button", { name: /Note #\d+/ })).toBeVisible()
//     await expect(page.getByText("Your Notes (1)")).toBeVisible()
//   })

//   test("can open a note and see its details", async ({ page }) => {
//     await page.getByLabel("Title").fill("Detail test")
//     await page.getByLabel("Body").fill("Content to verify")
//     await page.getByLabel(/Tags/).fill("tag1")
//     await page.getByRole("button", { name: "Create Note" }).click()

//     await page.getByRole("button", { name: /Note #\d+/ }).click()

//     await expect(
//       page.getByRole("heading", { name: "Note Details" }),
//     ).toBeVisible()
//     await expect(page.getByText("Title: Detail test")).toBeVisible()
//     await expect(page.getByText("Body: Content to verify")).toBeVisible()
//   })

//   test("filter by tag shows only matching notes", async ({ page }) => {
//     await page.getByLabel("Title").fill("Work note")
//     await page.getByLabel("Body").fill("Body one")
//     await page.getByLabel(/Tags/).fill("work, urgent")
//     await page.getByRole("button", { name: "Create Note" }).click()

//     await page.getByLabel("Title").fill("Personal note")
//     await page.getByLabel("Body").fill("Body two")
//     await page.getByLabel(/Tags/).fill("personal")
//     await page.getByRole("button", { name: "Create Note" }).click()

//     await expect(page.getByText("Your Notes (2)")).toBeVisible()

//     await page.getByPlaceholder("Filter by tag").fill("work")
//     await expect(page.getByText("Your Notes (1)")).toBeVisible()
//     await expect(page.getByRole("button", { name: "Note #1" })).toBeVisible()
//     await expect(page.getByRole("button", { name: "Note #2" })).not.toBeVisible()

//     await page.getByPlaceholder("Filter by tag").fill("nonexistent")
//     await expect(page.getByText("No notes match the filter")).toBeVisible()
//     await expect(page.getByText("Your Notes (0)")).toBeVisible()

//     await page.getByPlaceholder("Filter by tag").fill("")
//     await expect(page.getByText("Your Notes (2)")).toBeVisible()
//   })
// })
