import { expect, test } from '@playwright/test';

test.use({ actionTimeout: 15_000 });

test('rejects invalid personnel-code credentials', async ({ page }) => {
  await page.goto('/user/login');
  await page.getByLabel('Personnel code', { exact: true }).fill('unknown-personnel-code');
  await page.getByLabel('Password', { exact: true }).fill('incorrect-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Incorrect personnel code or password.');
  await expect(page).toHaveURL(/\/user\/login/);
});

test('manages device, test and signal definitions through the real API', async ({ page, context }) => {
  test.skip(!process.env.E2E_PERSONNEL_CODE || !process.env.E2E_PASSWORD, 'Supply test login credentials.');
  const marker = `ui-test-${Date.now()}`;
  const created: { resource: string; id: string }[] = [];

  try {
    await page.goto('/user/login');
    await page.getByLabel('Personnel code', { exact: true }).fill(process.env.E2E_PERSONNEL_CODE || '');
    await page.getByLabel('Password', { exact: true }).fill(process.env.E2E_PASSWORD || '');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page).toHaveURL(/\/backend-status/);
    await page.reload();
    await expect(page.getByRole('link', { name: /Device types$/ })).toBeVisible();

    await page.getByRole('link', { name: /Device types$/ }).click();
    await page.getByRole('button', { name: /New device type$/ }).click();
    let dialog = page.getByRole('dialog');
    await dialog.getByLabel('Name', { exact: true }).fill(marker);
    let saved = page.waitForResponse((response) =>
      response.url().endsWith('/api/device-types/') && response.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    let response = await saved;
    expect(response.status()).toBe(201);
    created.push({ resource: 'device-types', id: (await response.json()).id });
    await expect(page.getByRole('row').filter({ hasText: marker })).toBeVisible();

    await page.getByRole('link', { name: /Test definitions$/ }).click();
    await page.getByRole('button', { name: /New test definition$/ }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByLabel('Name', { exact: true }).fill(marker + '-test');
    await dialog.getByRole('combobox', { name: 'Device type', exact: true }).fill(marker);
    await page.locator('.ant-select-dropdown').getByText(marker, { exact: true }).click();
    await dialog.getByLabel('Sample rate (Hz)', { exact: true }).fill('1000');
    saved = page.waitForResponse((item) =>
      item.url().endsWith('/api/test-definitions/') && item.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    response = await saved;
    expect(response.status()).toBe(201);
    created.push({ resource: 'test-definitions', id: (await response.json()).id });

    await page.getByRole('row').filter({ hasText: marker + '-test' })
      .getByRole('button', { name: 'Edit', exact: true }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByLabel('Sample rate (Hz)', { exact: true }).fill('500');
    const updated = page.waitForResponse((item) =>
      item.url().includes('/api/test-definitions/') && item.request().method() === 'PATCH');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    expect((await updated).status()).toBe(200);

    await page.getByRole('link', { name: /Signal definitions$/ }).click();
    await page.getByRole('button', { name: /New signal definition$/ }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByLabel('Name', { exact: true }).fill(marker + '-signal');
    await dialog.getByRole('combobox', { name: 'Test', exact: true }).fill(marker + '-test');
    await page.locator('.ant-select-dropdown')
      .getByText(marker + ' / ' + marker + '-test', { exact: true }).click();
    saved = page.waitForResponse((item) =>
      item.url().endsWith('/api/signal-definitions/') && item.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    response = await saved;
    expect(response.status()).toBe(201);
    created.push({ resource: 'signal-definitions', id: (await response.json()).id });
    await expect(page.getByRole('row').filter({ hasText: marker + '-signal' })).toBeVisible();

    for (const [menu, name] of [
      ['Signal definitions', marker + '-signal'],
      ['Test definitions', marker + '-test'],
      ['Device types', marker],
    ]) {
      await page.getByRole('link', { name: new RegExp(`${menu}$`) }).click();
      await page.getByRole('row').filter({ hasText: name })
        .getByRole('button', { name: 'Delete', exact: true }).click();
      await page.getByRole('tooltip').getByRole('button', { name: 'Delete', exact: true }).click();
      await expect(page.getByRole('row').filter({ hasText: name })).toHaveCount(0);
    }

    await page.getByRole('button', { name: 'Account menu', exact: true }).click();
    await page.getByText('Sign out', { exact: true }).click();
    await expect(page).toHaveURL(/\/user\/login/);
    await page.goto('/device-types');
    await expect(page).toHaveURL(/\/user\/login/);
  } finally {
    const token = (await context.cookies()).find((cookie) => cookie.name === 'csrftoken')?.value || '';
    for (const item of created.reverse()) {
      await page.request.delete(`/backend/api/${item.resource}/${item.id}/`, {
        headers: { 'X-CSRFToken': token },
      });
    }
  }
});
