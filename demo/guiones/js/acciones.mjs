const cajaFrase = (frase) => {
  const el = document.querySelector('.select-text');
  const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const i = n.data.indexOf(frase);
    if (i < 0) continue;
    const r = document.createRange();
    r.setStart(n, i);
    r.setEnd(n, i + frase.length);
    const c = r.getClientRects();
    const a = c[0];
    const b = c[c.length - 1];
    return { x1: a.left + 1, y1: a.top + a.height / 2, x2: b.right - 1, y2: b.top + b.height / 2 };
  }
  return null;
};

export default async (v, lib, args) => {
  const { page } = v;
  switch (args.accion) {
    case 'seleccionar': {
      await page.locator('.select-text').first().scrollIntoViewIfNeeded();
      await lib.pausa(500);
      const p = await page.evaluate(`(${cajaFrase})(${JSON.stringify(args.frase)})`);
      if (!p) throw new Error(`acciones.mjs: no aparece "${args.frase}"`);
      await lib.moverA(page, p.x1, p.y1, 800);
      await page.mouse.down();
      await lib.moverA(page, p.x2, p.y2, args.ms ?? 900);
      await page.mouse.up();
      await lib.pausa(500);
      return;
    }
    case 'misma_pestana':
      await page.evaluate(() =>
        document.querySelectorAll('a[target="_blank"]').forEach((a) => a.removeAttribute('target')),
      );
      return;
    case 'volver':
      await page.goBack({ waitUntil: 'load' });
      return;
    default:
      throw new Error(`acciones.mjs: acción desconocida "${args.accion}"`);
  }
};
