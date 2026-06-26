import { test, expect, request as playwrightRequest } from '@playwright/test';

/**
 * E2E tests for FinAlly.
 *
 * IMPORTANT: Tests run sequentially against a live Docker container with a
 * persistent SQLite DB. To avoid state bleed between runs, each test that
 * mutates state uses tickers that do not conflict with other tests.
 *
 * State assumptions at test start:
 * - App is running at http://localhost:8080
 * - LLM_MOCK=true (chat returns deterministic mock response)
 * - Market simulator is running (prices stream via SSE)
 * - DB may have state from previous test runs
 */

// Ensure a clean-enough state: add AMZN if missing, remove PLTR if present
test.beforeAll(async () => {
  const ctx = await playwrightRequest.newContext({ baseURL: 'http://localhost:8080' });

  // Ensure AMZN is in watchlist (for remove test)
  const wl = await ctx.get('/api/watchlist');
  const tickers: string[] = (await wl.json()).map((t: { ticker: string }) => t.ticker);

  if (!tickers.includes('AMZN')) {
    await ctx.post('/api/watchlist', { data: { ticker: 'AMZN' } });
  }
  // Remove PLTR if it was added by a previous run
  if (tickers.includes('PLTR')) {
    await ctx.delete('/api/watchlist/PLTR');
  }

  await ctx.dispose();
});

// Test 7: API Health (API-only, no browser)
test('API: health, watchlist, portfolio', async () => {
  const ctx = await playwrightRequest.newContext({ baseURL: 'http://localhost:8080' });

  const health = await ctx.get('/api/health');
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).status).toBe('ok');

  const watchlist = await ctx.get('/api/watchlist');
  expect(watchlist.ok()).toBeTruthy();
  const tickers = await watchlist.json();
  expect(Array.isArray(tickers)).toBeTruthy();
  expect(tickers.length).toBeGreaterThanOrEqual(9); // at least 9 after potential removals

  const portfolio = await ctx.get('/api/portfolio');
  expect(portfolio.ok()).toBeTruthy();
  const pf = await portfolio.json();
  expect(pf).toHaveProperty('cash');
  expect(pf.cash).toBeGreaterThan(0);

  await ctx.dispose();
});

// Test 1: Page load
test('Page load: title, watchlist visible, cash shown in header', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/FinAlly/i);

  // Watchlist section header
  await expect(page.getByText('WATCHLIST', { exact: true }).first()).toBeVisible();

  // At least one ticker appears in watchlist
  await expect(page.getByText('AAPL').first()).toBeVisible({ timeout: 10000 });

  // Header shows CASH label
  await expect(page.getByText('CASH').first()).toBeVisible({ timeout: 10000 });
});

// Test 2: Prices streaming
test('Prices streaming: price values appear in watchlist', async ({ page }) => {
  await page.goto('/');
  await page.waitForTimeout(3000);

  // Watchlist header visible
  await expect(page.getByText('WATCHLIST', { exact: true }).first()).toBeVisible();

  // At least one price span like "$192.50" appears
  const priceSpan = page.locator('span').filter({ hasText: /^\$\d+\.\d{2}$/ }).first();
  await expect(priceSpan).toBeVisible({ timeout: 5000 });
});

// Test 3: Add ticker to watchlist
test('Add ticker: PLTR appears after adding', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('AAPL').first()).toBeVisible({ timeout: 10000 });

  const addInput = page.getByPlaceholder('Add ticker...');
  await addInput.fill('PLTR');
  await addInput.press('Enter');

  await expect(page.getByText('PLTR').first()).toBeVisible({ timeout: 10000 });
});

// Test 4: Remove ticker from watchlist
test('Remove ticker: AMZN disappears after API removal', async ({ page, request: req }) => {
  await page.goto('/');
  // AMZN should be present (ensured by beforeAll)
  await expect(page.getByText('AMZN').first()).toBeVisible({ timeout: 10000 });

  // Remove via API
  const resp = await req.delete('/api/watchlist/AMZN');
  expect(resp.ok()).toBeTruthy();

  // Reload to reflect state
  await page.reload();
  await expect(page.getByText('WATCHLIST', { exact: true }).first()).toBeVisible({ timeout: 5000 });
  await page.waitForTimeout(500);

  // AMZN span should be gone from the watchlist
  await expect(page.locator('span').filter({ hasText: 'AMZN' })).toHaveCount(0, { timeout: 5000 });
});

// Test 5: Buy shares
test('Buy shares: success message appears after buying AAPL', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('AAPL').first()).toBeVisible({ timeout: 10000 });

  // Wait for SSE prices to arrive
  await page.waitForTimeout(3000);

  const tickerInput = page.getByPlaceholder(/TICKER/i);
  await tickerInput.fill('AAPL');

  const qtyInput = page.getByPlaceholder('Qty');
  await qtyInput.fill('1');

  await page.getByRole('button', { name: 'BUY' }).click();

  // Success message: "Bought 1 AAPL @ $xxx"
  await expect(page.getByText(/Bought 1 AAPL/i)).toBeVisible({ timeout: 10000 });
});

// Test 6: AI Chat
test('AI Chat: mock response appears for portfolio question', async ({ page }) => {
  await page.goto('/');

  const chatInput = page.getByPlaceholder('Ask FinAlly...');
  await expect(chatInput).toBeVisible({ timeout: 5000 });

  await chatInput.fill('What is my portfolio?');
  await chatInput.press('Enter');

  // Mock response: "Your portfolio is looking healthy."
  await expect(page.getByText(/looking healthy/i)).toBeVisible({ timeout: 15000 });
});
