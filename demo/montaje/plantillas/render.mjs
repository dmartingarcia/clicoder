import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, rmSync } from 'node:fs';

const require = createRequire('/pw/node_modules/');
const { chromium } = require('playwright');

const SAL = '/salida';
const PLA = '/plantillas';
const P = JSON.parse(readFileSync(`${SAL}/params.json`, 'utf8'));
const FPS = 30;
if (!P.BASE) {
  const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const [a, b] = [rgb(P.A), rgb(P.B)];
  const base = [5, 6, 13];
  P.BASE = '#' + [0, 1, 2].map((i) => Math.round(((a[i] + b[i]) / 2) * 0.18 + base[i] * 0.82).toString(16).padStart(2, '0')).join('');
}

const leer = (f) => readFileSync(`${PLA}/${f}`, 'utf8');
const huella = (...partes) => createHash('sha1').update(partes.join('\u0001')).digest('hex');
const comunes = () => leer('comun.js') + leer('estilo.css');
const fuente = existsSync('/pw/node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2');
if (!fuente) console.log('Sin la fuente Inter en /pw: se usa la del sistema');

function enCache(dir, clave, n) {
  const f = `${dir}/.clave`;
  if (!existsSync(f) || readFileSync(f, 'utf8') !== clave) return false;
  return n == null || readdirSync(dir).filter((x) => /\.(jpg|png)$/.test(x)).length >= n;
}
function limpiar(dir) {
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
}

const nav = await chromium.launch();
async function pagina(html, ancho, alto, params) {
  const ctx = await nav.newContext({ viewport: { width: ancho, height: alto }, deviceScaleFactor: 1 });
  const pg = await ctx.newPage();
  pg.on('pageerror', (e) => console.log('[js]', String(e).slice(0, 200)));
  await pg.goto(`file://${PLA}/${html}`);
  await pg.evaluate((p) => window.setup(p), params);
  await pg.evaluate(async () => {
    await document.fonts.load("800 80px Inter");
    await document.fonts.load("500 40px Inter");
    await document.fonts.ready;
  });
  return pg;
}

async function secuencia(nombre, html, ancho, alto, params, n, calidad) {
  const dir = `${SAL}/${nombre}`;
  const clave = huella(JSON.stringify(params), n, comunes(), leer(html));
  if (enCache(dir, clave, n)) return console.log(`${nombre}: en caché (${n} fotogramas)`);
  limpiar(dir);
  const t0 = Date.now();
  const pg = await pagina(html, ancho, alto, params);
  for (let i = 0; i < n; i++) {
    await pg.evaluate((t) => window.render(t), i / FPS);
    await pg.screenshot({ path: `${dir}/${String(i + 1).padStart(4, '0')}.jpg`, type: 'jpeg', quality: calidad });
  }
  await pg.context().close();
  writeFileSync(`${dir}/.clave`, clave);
  console.log(`${nombre}: ${n} fotogramas en ${((Date.now() - t0) / 1000).toFixed(1)} s`);
}

async function capas() {
  const dir = `${SAL}/ventana`;
  const defs = [
    ['fondo', 1632, 962, true],
    ['mascara', 1632, 918, false],
    ['sombra', 1920, 1080, true],
    ['reflejo', 1632, 962, true],
  ];
  const clave = huella(JSON.stringify({ A: P.A, CF: P.CF, url: P.url }), comunes(), leer('ventana.html'));
  if (enCache(dir, clave, defs.length)) return console.log('ventana: en caché');
  limpiar(dir);
  for (const [capa, w, h, transparente] of defs) {
    const pg = await pagina('ventana.html', w, h, { capa, A: P.A, CF: P.CF, url: P.url });
    await pg.screenshot({ path: `${dir}/${capa}.png`, type: 'png', omitBackground: transparente });
    await pg.context().close();
  }
  writeFileSync(`${dir}/.clave`, clave);
  console.log('ventana: 4 capas');
}

const base = { A: P.A, B: P.B, ACC: P.ACC, TXT: P.TXT, BASE: P.BASE, marca: P.marca, tituloPx: P.tituloPx, subPx: P.subPx };

try {
  await secuencia('intro', 'intro.html', 1920, 1080,
    { ...base, titulo: P.titulo, sub: P.sub, dur: P.introS, t0: 0 }, Math.round(P.introS * FPS), 93);
  await secuencia('cierre', 'cierre.html', 1920, 1080,
    { ...base, c1: P.c1, c2: P.c2, c3: P.c3, dur: P.cierreS, t0: P.t0Cierre }, Math.round(P.cierreS * FPS), 93);
  await secuencia('malla', 'malla.html', 960, 540, { ...base, t0: P.t0Clip }, 8 * FPS, 95);
  await capas();
} finally {
  await nav.close();
}

if (P.musica) {
  const { generarMusica } = await import(`${PLA}/musica.mjs`);
  const clave = huella(JSON.stringify([P.totalS, P.bpm, P.escala, P.tonos]), readFileSync(`${PLA}/musica.mjs`, 'utf8'));
  const f = `${SAL}/musica.clave`;
  if (existsSync(f) && readFileSync(f, 'utf8') === clave && existsSync(`${SAL}/musica.wav`)) {
    console.log('música: en caché');
  } else {
    const t0 = Date.now();
    generarMusica({ dur: P.totalS, bpm: P.bpm, escala: P.escala, tonos: P.tonos, ruta: `${SAL}/musica.wav` });
    writeFileSync(f, clave);
    console.log(`música: ${P.totalS.toFixed(1)} s en ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  }
}
