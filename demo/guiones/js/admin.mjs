const CDN = 'https://cdn.tailwindcss.com/';
const cache = new Map();

const servir = async (route) => {
  const url = route.request().url();
  try {
    if (!cache.has(url)) {
      const r = await fetch(url);
      cache.set(url, {
        status: r.status,
        headers: { 'content-type': r.headers.get('content-type') ?? 'application/javascript' },
        body: Buffer.from(await r.arrayBuffer()),
      });
    }
    await route.fulfill(cache.get(url));
  } catch {
    await route.abort();
  }
};

export default async (v, lib, args = {}) => {
  const { page } = v;
  const base = args.url ?? process.env.BACKEND_URL ?? 'http://localhost:4000';
  switch (args.accion) {
    case 'preparar':
      await page.route(`${CDN}**`, servir);
      await fetch(CDN).then(async (r) => cache.set(CDN, {
        status: r.status,
        headers: { 'content-type': r.headers.get('content-type') ?? 'application/javascript' },
        body: Buffer.from(await r.arrayBuffer()),
      })).catch(() => {});
      return;
    case 'entrar': {
      await page.goto(`${base}/admin/login`, { waitUntil: 'load' });
      await page.locator('input[name="session[email]"]').fill(process.env.DEMO_EMAIL);
      await page.locator('input[name="session[password]"]').fill(process.env.DEMO_PASSWORD);
      await page.locator('button[type="submit"]').click();
      await page.waitForURL('**/admin/**', { timeout: 30000 });
      return;
    }
    default:
      throw new Error(`admin.mjs: acción desconocida "${args.accion}"`);
  }
};
