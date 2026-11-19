export default async (v, lib, args = {}) => {
  const url = args.url ?? process.env.GRAFANA_URL ?? 'http://host.docker.internal:3030';
  const { page } = v;
  await page.goto(`${url}/login`, { waitUntil: 'load' });
  await page.locator('input[name="user"]').fill(process.env.GRAFANA_USER ?? 'admin');
  await page.locator('input[name="password"]').fill(process.env.GRAFANA_PASSWORD ?? 'changeme');
  await page.locator('button[type="submit"]').click();
  await page.locator('[data-testid="data-testid Nav menu"], nav, .sidemenu').first().waitFor({ timeout: 30000 }).catch(() => {});
};
