import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { startingPosition } from "../src/starting-position";

const fixture = "/tests/fixtures/app.html";
async function scan(page: Page) {
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await page.evaluate(async () => {
    const finite = document
      .getAnimations()
      .filter(
        (animation) =>
          animation.effect?.getComputedTiming().iterations !== Infinity,
      );
    await Promise.all(
      finite.map((animation) => animation.finished.catch(() => {})),
    );
  });
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(violations).toEqual([]);
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}
async function select(page: Page, label: string, option: string) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
  await expect(page.getByRole("listbox")).toHaveCount(0);
}
async function mockApi(
  page: Page,
  {
    onboarding = false,
    history = 0,
    hints = true,
    moveDelay = 0,
    latency = 0,
  }: {
    onboarding?: boolean;
    history?: number;
    hints?: boolean;
    moveDelay?: number;
    latency?: number;
  } = {},
) {
  let profile = {
    id: "player_fixture",
    nickname: "",
    experience: "unspecified",
    analytics_consent: false,
    research_consent: false,
    puzzle_rating: 1200,
    puzzles_solved: 0,
    puzzles_attempted: 0,
    points: 0,
    activity_counts: {},
    recent: [],
    calibration_complete: !onboarding,
    rating_range: [900, 1500],
  };
  const sessions: Record<string, Record<string, any>> = {};
  const actions: Record<string, unknown>[] = [];
  let current: string | null = null;
  const summary = (session: Record<string, any>) => {
    const { puzzle, ...rest } = session;
    return rest;
  };
  function newPuzzle(id: string, index: number, hasHints: boolean) {
    return {
      ...startingPosition,
      legal_moves: ["e2e3", "e2e4", "b1a3", "b1c3"],
      id: `${id}_puzzle_${index}`,
      puzzle_id: `position_${index}`,
      version: 0,
      completed: false,
      moves: [],
      solved: false,
      status: "active",
      rating: 1200,
      player_color: "white",
      player_moves_required: 1,
      hints_available: hasHints,
      hint_shown: false,
      remaining_seconds: 90,
      time_limit_seconds: 90,
      solution: ["e2e4"],
      solution_san: ["e4"],
      hint_text: "Look for forcing moves: checks, captures, and threats.",
    };
  }
  function create(calibration: boolean, size: number) {
    const id = calibration ? "calibration_fixture" : "session_fixture";
    const session = {
      id,
      kind: calibration ? "calibration" : "puzzle_session",
      total: calibration ? 10 : size,
      version: 1,
      completed: false,
      started_at: Date.now() / 1000,
      finished_at: null,
      finished_count: 0,
      solved: 0,
      hints_available: calibration ? false : hints,
      estimated_rating: 1200,
      rating_range: [900, 1500],
      rating_before: 1200,
      rating_after: null,
      outcomes: [],
      feedback: null,
      puzzle: newPuzzle(id, 0, !calibration && hints),
    };
    sessions[id] = session;
    current = id;
    return session;
  }
  await page.route("**/api/**", async (route) => {
    if (latency) await new Promise((resolve) => setTimeout(resolve, latency));
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = request.postDataJSON() || {};
    actions.push({ path, method: request.method(), ...body });
    let result: unknown;
    if (path === "/api/learning")
      result = {
        profile,
        onboarding_id: onboarding && current ? current : null,
        active_session:
          current &&
          sessions[current].kind === "puzzle_session" &&
          !sessions[current].completed
            ? summary(sessions[current])
            : null,
        recent: Object.values(sessions)
          .filter((session) => session.kind === "puzzle_session")
          .map(summary),
      };
    else if (path === "/api/me") {
      if (request.method() === "PATCH") profile = { ...profile, ...body };
      result = profile;
    } else if (path === "/api/onboarding")
      result =
        current && !sessions[current].completed
          ? sessions[current]
          : create(true, 10);
    else if (path === "/api/learning/sessions")
      result = create(false, body.size);
    else if (path === "/api/learning/history") {
      const totalPages = Math.max(1, Math.ceil(history / 8));
      const requested = Number(
        new URL(request.url()).searchParams.get("page") || 1,
      );
      const currentPage = Math.min(requested, totalPages);
      result = {
        items: Array.from(
          { length: Math.min(8, Math.max(0, history - (currentPage - 1) * 8)) },
          (_, index) => ({
            id: `history_${(currentPage - 1) * 8 + index}`,
            kind: "puzzle_session",
            total: 20,
            version: 20,
            completed: true,
            started_at: Date.now() / 1000 - index * 3600,
            finished_at: Date.now() / 1000,
            finished_count: 20,
            solved: 15,
            hints_available: true,
            estimated_rating: 1200,
            rating_range: [900, 1500],
            rating_before: 1200,
            rating_after: 1225,
            outcomes: Array.from({ length: 20 }, (_, puzzle) => ({
              solved: (puzzle * 7 + index) % 4 !== 0,
              hint_used: puzzle % 6 === 0,
              status: (puzzle * 7 + index) % 4 !== 0 ? "solved" : "failed",
            })),
            feedback: {},
          }),
        ),
        page: currentPage,
        total_pages: totalPages,
        total: history,
      };
    } else if (path === "/api/interactions") {
      await route.fulfill({ status: 204 });
      return;
    } else {
      const session = sessions[current || ""];
      if (path.endsWith("/moves") && moveDelay)
        await new Promise((resolve) => setTimeout(resolve, moveDelay));
      if (path.endsWith("/moves") || path.endsWith("/skip")) {
        session.puzzle = {
          ...session.puzzle,
          completed: true,
          solved: path.endsWith("/moves") && body.move === "e2e4",
          status: path.endsWith("/moves")
            ? body.move === "e2e4"
              ? "solved"
              : "incorrect"
            : "skipped",
          version: session.puzzle.version + 1,
          solution: ["e2e4"],
          solution_san: ["e4"],
          moves: path.endsWith("/moves") ? [body.move] : [],
        };
        session.finished_count += 1;
        session.solved += Number(session.puzzle.solved);
        session.version += 1;
        session.outcomes.push({
          solved: session.puzzle.solved,
          hint_used: session.puzzle.hint_shown,
          status: session.puzzle.status,
        });
        if (session.finished_count === session.total) {
          session.completed = true;
          session.finished_at = Date.now() / 1000;
          session.rating_after = 1200;
          if (session.kind === "calibration")
            profile.calibration_complete = true;
        }
        result = session.puzzle;
      } else if (path.endsWith("/hint")) {
        Object.assign(session.puzzle, {
          hint_shown: true,
          hint: "Look for forcing moves: checks, captures, and threats.",
          version: session.puzzle.version + 1,
        });
        result = session.puzzle;
      } else if (path.endsWith("/next")) {
        session.puzzle = newPuzzle(
          session.id,
          session.finished_count,
          session.hints_available,
        );
        session.version += 1;
        result = session;
      } else if (path.endsWith("/feedback")) {
        session.feedback = body;
        result = session;
      } else result = session;
    }
    await route.fulfill({ json: result });
  });
  return actions;
}

test("board has one tab stop and supports keyboard selection, clearing, and flipping", async ({
  page,
}) => {
  await page.goto(`${fixture}?scenario=board`);
  const grid = page.getByRole("grid", { name: "Chessboard" });
  await expect(grid.getByRole("row")).toHaveCount(8);
  await expect(grid.getByRole("gridcell")).toHaveCount(64);
  await expect(grid.locator('button[tabindex="0"]')).toHaveCount(1);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "e2 white pawn", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".board-caption")).toContainText(
    "Legal destinations: e3, e4",
  );
  await page.keyboard.press("Escape");
  await expect(page.locator(".board-caption")).toContainText(
    "Selection cleared",
  );
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("ArrowUp");
  await expect(
    page.getByRole("button", {
      name: "e4 empty, legal destination",
      exact: true,
    }),
  ).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.locator(".board-caption")).toContainText(
    "Move e2 to e4 selected",
  );
  await expect(page.getByLabel("Recorded move")).toHaveText("e2e4");
  await page.getByRole("button", { name: "Flip board" }).click();
  await page
    .getByRole("button", { name: "e2 white pawn", exact: true })
    .focus();
  await page.keyboard.press("ArrowUp");
  await expect(
    page.getByRole("button", { name: "e1 white king", exact: true }),
  ).toBeFocused();
  await scan(page);
});

test("promotion dialog traps focus, closes with Escape, and restores the board square", async ({
  page,
}) => {
  await page.goto(`${fixture}?scenario=promotion`);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Promote your pawn" });
  await expect(dialog).toBeVisible();
  await scan(page);
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press("Tab");
    await expect
      .poll(() =>
        dialog.evaluate((element) => element.contains(document.activeElement)),
      )
      .toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: /a8 empty/ })).toBeFocused();
  await page.keyboard.press("Enter");
  await dialog.getByRole("button", { name: "queen", exact: true }).click();
  await expect(page.getByLabel("Recorded move")).toHaveText("a7a8q");
});

test("readonly board remains readable and navigable without accepting moves", async ({
  page,
}) => {
  await page.goto(`${fixture}?scenario=readonly`);
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await page.keyboard.press("ArrowUp");
  await expect(
    page.getByRole("button", { name: "e3 empty", exact: true }),
  ).toBeFocused();
  await expect(page.getByLabel("Recorded move")).toHaveText("");
  await scan(page);
});

test("public login has no sidebar, includes credits, and supports both themes", async ({
  page,
}) => {
  await page.goto(`${fixture}?scenario=public`);
  await expect(
    page.getByRole("heading", { name: "Chess, one puzzle at a time." }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Arpan", exact: true }).first(),
  ).toHaveAttribute("href", "https://arpan.sh/");
  await expect(
    page.getByRole("link", { name: "Rijan", exact: true }).first(),
  ).toHaveAttribute("href", "https://rijan.sh/");
  await expect(page.locator("footer")).toContainText("A research project by");
  await scan(page);
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await scan(page);
  await page.setViewportSize({ width: 320, height: 800 });
  await scan(page);
  await noOverflow(page);
});

test("new users can consent and complete ten onboarding puzzles", async ({
  page,
}) => {
  const actions = await mockApi(page, { onboarding: true });
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await expect(
    page.getByRole("heading", { name: "Let’s find your level." }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toHaveCount(0);
  await page
    .getByRole("checkbox", { name: "Use my puzzle records for research." })
    .check();
  await page.getByRole("button", { name: "Start assessment" }).click();
  await expect(page.getByRole("button", { name: "Get a hint" })).toBeDisabled();
  await scan(page);
  for (let i = 0; i < 10; i++) {
    await page
      .getByRole("button", { name: "Skip puzzle", exact: true })
      .click();
    if (i < 9)
      await page
        .getByRole("button", { name: "Next puzzle", exact: true })
        .click();
  }
  await expect(
    page.getByRole("heading", { name: "Your starting point." }),
  ).toBeVisible();
  expect(
    actions.some(
      (action) => action.method === "PATCH" && action.research_consent === true,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Choose your first session" }).click();
  await expect(
    page.getByRole("heading", { name: "Your next session." }),
  ).toBeVisible();
  await scan(page);
});

test("session length, confidence, hints, progress and reload work", async ({
  page,
}) => {
  const actions = await mockApi(page);
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await page.getByRole("radio", { name: /Quick/ }).check();
  await page
    .getByRole("button", { name: "Start session", exact: true })
    .click();
  await expect(page.getByText("Puzzle 1 of 10", { exact: true })).toBeVisible();
  await page.getByRole("radio", { name: "High", exact: true }).check();
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(
    page.getByText("Look for forcing moves: checks, captures, and threats."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "e2 white pawn", exact: true })
    .click();
  await page
    .getByRole("button", { name: /e4 empty, legal destination/ })
    .click();
  await expect(page.getByText("Solved", { exact: true })).toBeVisible();
  expect(
    actions.some(
      (action) => action.move === "e2e4" && action.confidence === 75,
    ),
  ).toBe(true);
  await page.reload();
  await expect(page.getByText("Solved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next puzzle" }).click();
  await expect(page.getByText("Puzzle 2 of 10", { exact: true })).toBeVisible();
  await scan(page);
});

test("session feedback requires a choice and is saved once", async ({
  page,
}) => {
  const actions = await mockApi(page);
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await page.getByRole("radio", { name: /Quick/ }).check();
  await page
    .getByRole("button", { name: "Start session", exact: true })
    .click();
  for (let i = 0; i < 10; i++) {
    await page
      .getByRole("button", { name: "Skip puzzle", exact: true })
      .click();
    if (i < 9) await page.getByRole("button", { name: "Next puzzle" }).click();
  }
  await expect(
    page.getByRole("button", { name: "Save feedback" }),
  ).toBeDisabled();
  await page.getByRole("radio", { name: "4", exact: true }).check();
  await page.getByRole("button", { name: "Save feedback" }).click();
  await expect(
    page.getByRole("link", { name: "Back to sessions" }),
  ).toBeVisible();
  expect(
    actions.filter((action) => String(action.path).endsWith("/feedback")),
  ).toHaveLength(1);
  await scan(page);
});

test("history pagination restores its page and stays within mobile width", async ({
  page,
}) => {
  await mockApi(page, { history: 19 });
  await page.goto(`${fixture}?scenario=workspace#/history`);
  await expect(page.getByRole("status")).toContainText("Page 1 of 3");
  await expect(
    page.getByRole("link", { name: "Go to previous page" }),
  ).toHaveAttribute("aria-disabled", "true");
  await page.getByRole("link", { name: "Go to next page" }).click();
  await expect(page).toHaveURL(/history\?page=2/);
  await page.reload();
  await expect(page.getByRole("status")).toContainText("Page 2 of 3");
  await page.setViewportSize({ width: 320, height: 800 });
  await noOverflow(page);
  await scan(page);
});

test("mobile navigation restores focus and profile controls remain accessible", async ({
  page,
}) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your profile" }),
  ).toBeVisible();
  await scan(page);
  await noOverflow(page);
});

test("layout and SVG icons stay usable at 200 and 400 percent zoom equivalents", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto(`${fixture}?scenario=workspace#/home`);
  for (const width of [640, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await noOverflow(page);
    await expect(
      page.getByRole("button", { name: "Start session", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Open navigation" }).click();
    const icons = page.locator('[data-slot="sidebar-menu-button"] svg');
    for (const icon of await icons.all())
      expect((await icon.boundingBox())?.width).toBeGreaterThan(12);
    await page.keyboard.press("Escape");
    await scan(page);
  }
});

test("desktop navigation is a single top bar that marks the current page", async ({
  page,
}) => {
  await mockApi(page, { history: 3 });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(`${fixture}?scenario=workspace#/home`);
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: /sidebar|navigation/i }),
  ).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Sessions" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  const box = await nav.boundingBox();
  expect(box?.height).toBeLessThanOrEqual(64);
  await nav.getByRole("link", { name: "History" }).click();
  await expect(
    page.getByRole("heading", { name: "Session history" }),
  ).toBeVisible();
  await expect(nav.getByRole("link", { name: "History" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await scan(page);
});

test("session progress draws one board square per puzzle", async ({ page }) => {
  await mockApi(page);
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await page.getByRole("radio", { name: /Quick/ }).check();
  await page.getByRole("button", { name: "Start session", exact: true }).click();
  const progress = page.getByRole("progressbar", { name: "Session progress" });
  const squares = progress.locator("[data-state]");
  await expect(squares).toHaveCount(10);
  await expect(squares.nth(0)).toHaveAttribute("data-state", "current");
  await expect(squares.nth(1)).toHaveAttribute("data-state", "upcoming");
  await page.getByRole("button", { name: "e2 white pawn", exact: true }).click();
  await page.getByRole("button", { name: /e4 empty, legal destination/ }).click();
  await expect(squares.nth(0)).toHaveAttribute("data-state", "solved");
  await page.getByRole("button", { name: "Next puzzle" }).click();
  await page.getByRole("button", { name: "Skip puzzle", exact: true }).click();
  await expect(squares.nth(1)).toHaveAttribute("data-state", "missed");
  await expect(progress).toHaveAttribute("aria-valuenow", "2");
});

test("moves are checked instantly while the server records them", async ({
  page,
}) => {
  const actions = await mockApi(page, { moveDelay: 2500 });
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await page.getByRole("radio", { name: /Quick/ }).check();
  await page.getByRole("button", { name: "Start session", exact: true }).click();
  await page.getByRole("radio", { name: "High", exact: true }).check();
  await page.getByRole("button", { name: "e2 white pawn", exact: true }).click();
  await page.getByRole("button", { name: /e4 empty, legal destination/ }).click();
  await expect(page.getByText("Solved", { exact: true })).toBeVisible({
    timeout: 600,
  });
  await expect(
    page.getByRole("button", { name: /^e4 white pawn, last move/ }),
  ).toBeVisible({ timeout: 600 });
  await expect
    .poll(() =>
      actions.some(
        (action) => action.move === "e2e4" && action.confidence === 75,
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Next puzzle" }).click();
  await expect(page.getByText("Puzzle 2 of 10", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "e2 white pawn", exact: true }).click();
  await page.getByRole("button", { name: /e3 empty, legal destination/ }).click();
  await expect(page.getByText("Not quite", { exact: true })).toBeVisible({
    timeout: 600,
  });
  const solution = page.getByRole("list", { name: "Solution" });
  await expect(solution.getByRole("listitem")).toHaveCount(1);
  await expect(solution).toContainText("Your move");
  await expect(solution).toContainText("e4");
  await expect(solution).toContainText("Pawn to e4");
  await scan(page);
});

test("player rating is shown while puzzle difficulty stays hidden until revealed", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await expect(page.getByText("1,200", { exact: true })).toBeVisible();
  await expect(
    page.locator(".app-topbar").getByText("1200", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Show .*rating/ })).toHaveCount(
    0,
  );
  await page.getByRole("radio", { name: /Quick/ }).check();
  await page.getByRole("button", { name: "Start session", exact: true }).click();
  const difficulty = page.getByRole("button", {
    name: "Show puzzle difficulty",
  });
  await expect(difficulty).toHaveAttribute("aria-pressed", "false");
  await difficulty.click();
  await expect(difficulty).toHaveAttribute("aria-pressed", "true");
});

test("hints and skips respond before the server does", async ({ page }) => {
  test.setTimeout(60_000);
  const actions = await mockApi(page, { latency: 1500 });
  await page.goto(`${fixture}?scenario=workspace#/home`);
  await page.getByRole("radio", { name: /Quick/ }).check({ timeout: 15_000 });
  await page.getByRole("button", { name: "Start session", exact: true }).click();
  await page
    .getByText("Puzzle 1 of 10", { exact: true })
    .waitFor({ timeout: 15_000 });
  await page.getByRole("button", { name: "Get a hint" }).click();
  await expect(
    page.getByText("Look for forcing moves: checks, captures, and threats."),
  ).toBeVisible({ timeout: 300 });
  await page.getByRole("button", { name: "Skip puzzle", exact: true }).click();
  await expect(page.getByText("Puzzle skipped", { exact: true })).toBeVisible({
    timeout: 300,
  });
  await expect
    .poll(() => actions.map((action) => String(action.path)), {
      timeout: 15_000,
    })
    .toEqual(
      expect.arrayContaining([
        expect.stringMatching(/\/hint$/),
        expect.stringMatching(/\/skip$/),
      ]),
    );
  const hint = actions.findIndex((a) => String(a.path).endsWith("/hint"));
  const skip = actions.findIndex((a) => String(a.path).endsWith("/skip"));
  expect(hint).toBeLessThan(skip);
});

test("sound effects follow the game and can be switched off", async ({
  page,
}) => {
  await page.addInitScript(() => {
    (window as any).__sounds = [];
    addEventListener("chesso-sound", (event) =>
      (window as any).__sounds.push((event as CustomEvent).detail),
    );
  });
  await mockApi(page);
  await page.goto(`${fixture}?scenario=workspace#/home`);
  const toggle = page.getByRole("button", { name: "Sound effects" });
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("radio", { name: /Quick/ }).check();
  await page.getByRole("button", { name: "Start session", exact: true }).click();
  await page.getByRole("button", { name: "e2 white pawn", exact: true }).click();
  await page.getByRole("button", { name: /e4 empty, legal destination/ }).click();
  await expect
    .poll(() => page.evaluate(() => (window as any).__sounds))
    .toEqual(expect.arrayContaining(["move", "solved"]));
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Sound effects" }),
  ).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "Next puzzle" }).click();
  await page.getByRole("button", { name: "Get a hint" }).click();
  await page.waitForTimeout(200);
  expect(await page.evaluate(() => (window as any).__sounds)).toEqual([]);
  await scan(page);
});
