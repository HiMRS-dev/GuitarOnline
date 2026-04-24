import { expect, test } from "@playwright/test";

const TEACHER_ID = "7d1404cd-cfdf-45f5-9f5e-1d62f6f9f001";
const PROFILE_ID = "c2258a73-22df-42be-98d8-4f3afe9e8ec1";
const USER_ID = "8a581ad4-e767-4dfe-a8b4-5298f2f98873";

function jsonHeaders() {
  return {
    "content-type": "application/json"
  };
}

test("admin login and platform teachers page smoke flow", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === "POST" && path === "/api/v1/identity/auth/login") {
      await route.fulfill({
        status: 200,
        headers: jsonHeaders(),
        body: JSON.stringify({
          access_token: "mock-admin-access-token",
          refresh_token: "mock-admin-refresh-token",
          token_type: "bearer"
        })
      });
      return;
    }

    if (method === "GET" && path === "/api/v1/identity/users/me") {
      const authHeader = request.headers()["authorization"] ?? "";
      if (authHeader !== "Bearer mock-admin-access-token") {
        await route.fulfill({
          status: 401,
          headers: jsonHeaders(),
          body: JSON.stringify({ detail: "Unauthorized" })
        });
        return;
      }

      await route.fulfill({
        status: 200,
        headers: jsonHeaders(),
        body: JSON.stringify({
          id: USER_ID,
          email: "admin-smoke@guitaronline.dev",
          timezone: "UTC",
          is_active: true,
          role: {
            id: "role-admin",
            name: "admin"
          },
          created_at: "2026-03-10T00:00:00Z",
          updated_at: "2026-03-10T00:00:00Z"
        })
      });
      return;
    }

    if (method === "POST" && path === "/api/v1/identity/auth/refresh") {
      await route.fulfill({
        status: 401,
        headers: jsonHeaders(),
        body: JSON.stringify({ detail: "Unauthorized" })
      });
      return;
    }

    if (method === "GET" && path === "/api/v1/admin/teachers") {
      await route.fulfill({
        status: 200,
        headers: jsonHeaders(),
        body: JSON.stringify({
          items: [
            {
              teacher_id: TEACHER_ID,
              profile_id: PROFILE_ID,
              email: "teacher-smoke@guitaronline.dev",
              full_name: "Smoke Teacher Full Name",
              display_name: "Smoke Teacher",
              timezone: "Europe/Moscow",
              status: "active",
              is_active: true,
              tags: ["fingerstyle"],
              created_at_utc: "2026-03-10T00:00:00Z",
              updated_at_utc: "2026-03-10T00:00:00Z"
            }
          ],
          limit: 50,
          offset: 0,
          total: 1
        })
      });
      return;
    }

    if (method === "GET" && path === `/api/v1/admin/teachers/${TEACHER_ID}`) {
      await route.fulfill({
        status: 200,
        headers: jsonHeaders(),
        body: JSON.stringify({
          teacher_id: TEACHER_ID,
          profile_id: PROFILE_ID,
          email: "teacher-smoke@guitaronline.dev",
          full_name: "Smoke Teacher Full Name",
          display_name: "Smoke Teacher",
          timezone: "Europe/Moscow",
          status: "active",
          is_active: true,
          tags: ["fingerstyle"],
          created_at_utc: "2026-03-10T00:00:00Z",
          updated_at_utc: "2026-03-10T00:00:00Z",
          bio: "Smoke profile",
          experience_years: 8
        })
      });
      return;
    }

    if (method === "GET" && path === `/api/v1/admin/teachers/${TEACHER_ID}/schedule`) {
      await route.fulfill({
        status: 200,
        headers: jsonHeaders(),
        body: JSON.stringify({
          teacher_id: TEACHER_ID,
          timezone: "Europe/Moscow",
          windows: []
        })
      });
      return;
    }

    if (method === "POST" && path === "/api/v1/identity/auth/logout") {
      await route.fulfill({
        status: 204,
        body: ""
      });
      return;
    }

    await route.fulfill({
      status: 404,
      headers: jsonHeaders(),
      body: JSON.stringify({ detail: `Unhandled mock route: ${method} ${path}` })
    });
  });

  await page.goto("/admin");
  await expect(page).toHaveURL(/\/admin\/login$/);

  await page.locator('input[name="email"]').fill("admin-smoke@guitaronline.dev");
  await page.locator('input[name="password"]').fill("StrongPass123!");
  await page.locator('button[type="submit"]').click();

  await page.locator('a[href="/admin/platform"]').click();
  await expect(page).toHaveURL(/\/admin\/platform$/);

  await page.locator('a[href="/admin/platform/teachers"]').first().click();
  await expect(page).toHaveURL(/\/admin\/platform\/teachers(?:\?.*)?$/);
  await expect(page.getByText("Smoke Teacher Full Name")).toBeVisible();

  await page.getByText("Smoke Teacher Full Name").first().click();
  await expect(page).toHaveURL(new RegExp(`/admin/platform/teachers/${TEACHER_ID}/show$`));
  await expect(page.getByText("Teacher Detail")).toBeVisible();
  await expect(page.getByText("Smoke profile")).toBeVisible();
});
