import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const PAGINAS = path.resolve(aqui, '../../capturas/paginas');
const DATOS = path.resolve(aqui, '../../out/datos');
const leer = (f) => fs.readFileSync(path.join(DATOS, f), 'utf8').trimEnd();

export default async (v, lib, args = {}) => {
  const { page } = v;
  const { pausa, captura } = lib;
  switch (args.accion) {
    case 'abrir':
      await page.goto('file://' + path.join(PAGINAS, args.pagina));
      return;
    case 'arquitectura': {
      const total = await page.evaluate(() => window.total);
      for (let i = 1; i <= total; i++) {
        await page.evaluate((n) => window.paso(n), i);
        await pausa(args.pausa ?? 2400);
        if (args.capturas?.[i]) await captura(v, args.capturas[i]);
      }
      return;
    }
    case 'terminal': {
      if (args.limpiar) await page.evaluate(() => window.limpiar());
      if (args.titulo) await page.evaluate((t) => window.titulo(t), args.titulo);
      await page.evaluate((c) => window.teclear(c), args.comando);
      let salida = leer(args.fichero);
      if (args.lineas) salida = salida.split('\n').slice(0, args.lineas).join('\n');
      await page.evaluate(([t, ms]) => window.salida(t, ms), [salida, args.velocidad ?? 90]);
      await pausa(args.pausa ?? 1800);
      if (args.captura) await captura(v, args.captura);
      return;
    }
    default:
      throw new Error(`paginas.mjs: acción desconocida "${args.accion}"`);
  }
};
