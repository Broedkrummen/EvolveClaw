import { test, expect } from '@playwright/test';

test('native bundle reads production memory, shows evidence, disables and restores a rule', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Verify calendar confirmation', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: 'View evidence' }).click();
  await expect(page.getByText('Create an appointment', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Disable', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Restore', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Restore', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Disable', exact: true })).toBeVisible();
  await expect(page.getByText('Cost is unknown.', { exact: false })).toBeVisible();
  await page.screenshot({ path: 'artifacts/ui-memory-desktop.png', fullPage: true });
});

test('read-only access preserves inspection and rejects forged mutations', async ({ page }) => {
  await page.goto('/?readonly=1');
  await expect(page.getByRole('button', { name: 'Disable', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Pause learning' })).toBeDisabled();
  await page.getByRole('button', { name: 'View evidence' }).click();
  await expect(page.getByText('Create an appointment', { exact: false })).toBeVisible();
  const result = await page.evaluate(async () => await window.fixtureHost.request('plugins.sessionAction', { pluginId: 'evolveclaw', actionId: 'mutate', payload: { operation: 'pause', expectedRevision: 0 } }));
  expect(result.ok).toBe(false);
});

test('stale revisions preserve the page and provide refresh recovery', async ({ page, request }) => {
  await page.goto('/'); await expect(page.getByRole('button', { name: 'Disable', exact: true })).toBeVisible();
  await request.post('/external-change');
  await page.getByRole('button', { name: 'Disable', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Refresh');
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await expect(page.getByRole('alert')).toBeEmpty();
  await expect(page.getByRole('status')).toContainText('Learning paused');
  await page.getByRole('button', { name: 'Resume learning' }).click();
  await expect(page.getByRole('status')).toContainText('Learning active');
});

test('empty, offline, narrow and keyboard states are usable', async ({ page }) => {
  await page.goto('/?empty=1'); await expect(page.getByRole('status')).toContainText('No recorded scopes');
  await page.goto('/?offline=1'); await expect(page.getByRole('alert')).toContainText('unavailable');
  await page.setViewportSize({ width: 375, height: 812 }); await page.goto('/');
  await expect(page.getByRole('button', { name: 'Disable', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Refresh', exact: true }).focus();
  await page.keyboard.press('Enter'); await expect(page.getByRole('status')).toContainText('Learning active');
  await page.screenshot({ path: 'artifacts/ui-memory-mobile.png', fullPage: true });
});
