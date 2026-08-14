import { expect, test, type Page } from '@playwright/test';

/**
 * The journey the whole product exists to deliver:
 *
 *   register → log in → choose a course → open a lesson → practise →
 *   submit an answer → get feedback → mastery updates → recommendation appears
 *
 * Runs against the seeded database. See docs/DEVELOPMENT.md for how to start it.
 *
 * A note on locators: several visible labels are intentionally duplicated by an `sr-only`
 * element (a `<dt>` naming a `<dd>`, for instance), which is correct for screen readers and
 * ambiguous for Playwright's strict mode. Those assertions use `.first()` deliberately rather
 * than weakening the markup.
 */

const DEMO_STUDENT = 'student@hietrieneducation.vn';
const DEMO_PASSWORD = 'HietEdu2026!';

async function login(page: Page, email: string, password: string) {
  await page.goto('/en/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
}

test.describe('public site', () => {
  test('home page presents the offer and real curriculum figures', async ({ page }) => {
    await page.goto('/en');

    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      'Every student can be good at maths',
    );
    await expect(page.getByRole('link', { name: /Start practising free/i }).first()).toBeVisible();

    // These figures come from the API, so their presence proves the site is wired to real data.
    await expect(page.getByText('skills mapped').first()).toBeVisible();
    await expect(page.getByText('question templates').first()).toBeVisible();
  });

  test('curriculum is browsable without an account', async ({ page }) => {
    await page.goto('/en/courses');
    await expect(page.getByRole('heading', { name: 'Courses', exact: true })).toBeVisible();

    await page.getByRole('link', { name: /Mathematics — Grade 8/ }).first().click();
    // Generous timeout: on a cold dev server this is the first compile of the
    // /[locale]/courses/[slug] route, which can take longer than the default expect timeout.
    await expect(page).toHaveURL(/\/en\/courses\/math-8/, { timeout: 60_000 });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Mathematics — Grade 8');

    // Units come from the database, not hard-coded copy.
    await expect(page.getByRole('heading', { name: 'Linear Functions' })).toBeVisible();
  });

  test('language switch keeps you on the same page and translates it', async ({ page }) => {
    await page.goto('/en/courses');
    await page.getByRole('button', { name: /Change language/i }).click();
    await page.getByRole('link', { name: 'Tiếng Việt' }).click();

    await expect(page).toHaveURL(/\/vi\/courses/);
    await expect(page.getByRole('heading', { name: 'Khóa học', exact: true })).toBeVisible();
  });

  test('an unknown page returns a proper 404 in both languages', async ({ page }) => {
    const response = await page.goto('/en/no-such-page');
    expect(response?.status()).toBe(404);

    // A URL that matched no route has no locale to read, so the root 404 cannot pick a language
    // from the request. It leads with Vietnamese because that is the product's primary language,
    // and carries the English line beside it rather than guessing.
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Không tìm thấy trang');
    await expect(page.getByText(/cannot find that page/i)).toBeVisible();
    await expect(page.getByRole('link', { name: 'English' })).toBeVisible();
  });
});

test.describe('registration and the learning loop', () => {
  test('a new student can register, practise, and see mastery move', async ({ page }) => {
    // A unique address per run keeps repeated runs independent.
    const email = `e2e-${Date.now()}@example.com`;

    await page.goto('/en/register');
    await page.getByLabel('Full name').fill('E2E Student');
    await page.getByLabel('Email address').fill(email);
    await page.getByLabel('Password').fill('E2ePassword1');
    await page.getByRole('button', { name: 'Create account' }).click();

    await expect(page).toHaveURL(/\/en\/dashboard/, { timeout: 60_000 });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Welcome');

    // A brand new student is recommended something to start on.
    const recommendation = page.locator('a[href*="/practice/"]').first();
    await expect(recommendation).toBeVisible({ timeout: 30_000 });
    await recommendation.click();

    await expect(page).toHaveURL(/\/en\/practice\//, { timeout: 60_000 });

    // A question is served, with its position in the session shown.
    await expect(page.getByText(/Question 1 of/)).toBeVisible({ timeout: 60_000 });

    // A hint can be revealed before answering.
    const hintButton = page.getByRole('button', { name: /Show a hint/i });
    if (await hintButton.count()) {
      await hintButton.click();
    }

    await answerCurrentQuestion(page);

    // Feedback appears, and always reports the mastery movement.
    await expect(page.getByText(/Correct!|Not quite|Partly right/).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/Mastery \d+% → \d+%/)).toBeVisible();

    // The worked solution is released only after answering.
    await expect(page.getByText('How to solve it')).toBeVisible();

    // Advancing proves the session progresses.
    await page.getByRole('button', { name: /Next question/i }).click();
    await expect(page.getByText(/Question 2 of/)).toBeVisible({ timeout: 60_000 });
  });

  test('the seeded student sees real progress data', async ({ page }) => {
    await login(page, DEMO_STUDENT, DEMO_PASSWORD);
    await expect(page).toHaveURL(/\/en\/dashboard/, { timeout: 60_000 });

    await expect(page.getByText('Overall mastery').first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Questions answered').first()).toBeVisible();

    // The seeded student has a practice history, so mastery bars must be rendered.
    await expect(page.locator('[role="progressbar"]').first()).toBeVisible();

    await page.goto('/en/progress');
    await expect(page.getByRole('heading', { name: 'Your progress' })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator('[role="progressbar"]').first()).toBeVisible({ timeout: 30_000 });
  });

  test('a signed-in student sees a gated learning path on a course', async ({ page }) => {
    await login(page, DEMO_STUDENT, DEMO_PASSWORD);
    await expect(page).toHaveURL(/\/en\/dashboard/, { timeout: 60_000 });

    await page.goto('/en/courses/math-8');
    // The path replaces the static outline for signed-in students.
    await expect(
      page.getByText(/Ready to start|Locked|In progress|Mastered/).first(),
    ).toBeVisible({ timeout: 45_000 });
  });

  test('wrong credentials are rejected without revealing whether the account exists', async ({
    page,
  }) => {
    await login(page, 'definitely-not-a-user@example.com', 'WrongPassword1');
    // Next injects its own empty role="alert" route announcer, so scope to ours.
    await expect(page.getByRole('alert').filter({ hasText: /./ }).first()).toContainText(
      /do not match/i,
      { timeout: 30_000 },
    );
  });
});

test.describe('lessons', () => {
  test('a lesson renders its content blocks', async ({ page }) => {
    await page.goto('/en/lessons/lesson-math-8-gradient');

    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      'Gradient of a Straight Line',
    );
    await expect(page.getByText('What you will learn')).toBeVisible({ timeout: 30_000 });

    // Worked-example and summary blocks both render.
    await expect(page.getByText('Example', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Summary', { exact: true }).first()).toBeVisible();

    // The interactive figure is inline SVG, not an external embed.
    await expect(page.locator('svg[role="img"]').first()).toBeVisible();
  });
});

test.describe('tutoring enquiry', () => {
  test('a visitor can submit an enquiry without an account', async ({ page }) => {
    await page.goto('/en/tutoring/one-to-one');

    await page.getByLabel('Your name').fill('E2E Parent');
    await page.getByLabel('Email address').fill(`e2e-parent-${Date.now()}@example.com`);
    await page.getByRole('button', { name: /Register interest/i }).click();

    await expect(page.getByText(/Thank you/)).toBeVisible({ timeout: 30_000 });
  });
});

test.describe('staff areas', () => {
  test('a teacher sees class analytics and the question bank', async ({ page }) => {
    await login(page, 'hieu@hietrieneducation.vn', DEMO_PASSWORD);
    await expect(page).toHaveURL(/\/en\/teacher/, { timeout: 60_000 });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Teacher dashboard');
    await expect(page.getByText('Weakest skills').first()).toBeVisible({ timeout: 45_000 });

    await page.goto('/en/teacher/questions');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Question bank', {
      timeout: 60_000,
    });

    // Previewing regenerates a live variant including its answer — teacher-only information.
    await page.getByRole('button', { name: /^Preview$/i }).first().click();
    await expect(page.getByText('Answer', { exact: true })).toBeVisible({ timeout: 30_000 });
  });

  test('a student cannot reach the teacher area', async ({ page }) => {
    await login(page, DEMO_STUDENT, DEMO_PASSWORD);
    await expect(page).toHaveURL(/\/en\/dashboard/, { timeout: 60_000 });

    await page.goto('/en/teacher');
    // The role guard bounces a non-teacher back to their own dashboard.
    await expect(page).toHaveURL(/\/en\/dashboard/, { timeout: 45_000 });
  });

  test('a parent sees their children', async ({ page }) => {
    await login(page, 'parent@hietrieneducation.vn', DEMO_PASSWORD);
    await expect(page).toHaveURL(/\/en\/parent/, { timeout: 60_000 });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Parent dashboard');
    await expect(page.getByText('An Nguyễn').first()).toBeVisible({ timeout: 45_000 });
  });
});

/** Fill in whatever input the current question type requires and submit. */
/**
 * Answer whatever the recommender served, whichever type it is.
 *
 * Which question a new student gets is chosen by the adaptive recommender, so this has to cover
 * every input shape the exercise engine can produce — "Check answer" stays disabled until the
 * answer is complete, and a type this helper cannot fill makes the most valuable test in the
 * suite fail at random. Matching questions in particular use one `<select>` per left-hand item
 * and are only complete once *every* one of them is set.
 */
async function answerCurrentQuestion(page: Page) {
  // "Question 1 of N" appears with the question card, but the variant's inputs arrive a beat
  // later. Branching on `count()` before then finds nothing anywhere and falls through to the
  // ordering case, which waits twenty seconds for a button that was never going to be there —
  // an intermittent failure in the most valuable test in the suite, with a misleading message.
  // An ordering question has no input at all — its controls are the reorder buttons — so it has
  // to be part of what we wait for, or this wait becomes its own timeout.
  await expect(
    page
      .locator('main input, main select, main textarea')
      .or(page.getByRole('button', { name: /Move .* down/i }))
      .first(),
  ).toBeVisible({ timeout: 30_000 });

  const radio = page.locator('input[type="radio"]').first();
  const checkbox = page.locator('input[type="checkbox"]').first();
  const selects = page.locator('select');
  const textboxes = page.getByRole('textbox');

  if (await radio.count()) {
    await radio.click({ force: true });
  } else if (await checkbox.count()) {
    await checkbox.click({ force: true });
  } else if (await selects.count()) {
    // matching: every pair must be chosen, and index 0 is the empty placeholder.
    for (let i = 0; i < (await selects.count()); i += 1) {
      const options = selects.nth(i).locator('option');
      await selects.nth(i).selectOption({ index: Math.min(1, (await options.count()) - 1) });
    }
  } else if (await textboxes.count()) {
    // fill_blank has one box per blank and needs all of them.
    for (let i = 0; i < (await textboxes.count()); i += 1) {
      await textboxes.nth(i).fill('4');
    }
  } else {
    // ordering: the list starts in an arbitrary order, which already counts as an answer once
    // it has been touched. Nudging the first item down is the smallest interaction that does it.
    const move = page.getByRole('button', { name: /Move .* down/i });
    if (!(await move.count())) {
      // Any other shape means this helper has fallen behind the exercise engine. Saying so beats
      // a twenty-second timeout on a locator that was never going to appear.
      const controls = await page
        .locator('main input, main select, main textarea')
        .evaluateAll((nodes) =>
          nodes.map((node) => `${node.tagName.toLowerCase()}[${(node as HTMLInputElement).type ?? ''}]`),
        );
      const prompt = (await page.locator('main').innerText()).slice(0, 300);
      throw new Error(
        `answerCurrentQuestion cannot fill the served question. Controls: ${controls.join(', ') || 'none'}\n${prompt}`,
      );
    }
    await move.first().click();
  }

  const check = page.getByRole('button', { name: /Check answer/i });
  await expect(check).toBeEnabled({ timeout: 15_000 });
  await check.click();
}
