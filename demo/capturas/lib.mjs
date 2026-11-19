import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
export const OUT = process.env.DEMO_OUT || path.resolve(AQUI, '../out');
export const BASE_URL = process.env.BASE_URL || 'http://localhost:3100';
export const MAILPIT_URL = process.env.MAILPIT_URL || 'http://host.docker.internal:8025';
export let ANCHO = 1920;
export let ALTO = 1080;

export const rx = (p) => new RegExp(p, 'i');

let RITMO = 1;
export function setRitmo(r) {
  const n = Number(r);
  RITMO = Number.isFinite(n) && n > 0 ? Math.min(Math.max(n, 0.1), 3) : 1;
  return RITMO;
}
export const pausaFija = (ms) => new Promise((r) => setTimeout(r, Math.max(0, ms)));
export const pausa = (ms) => pausaFija(Math.round(ms * RITMO));

export const TEMA_DEFECTO = {
  colores: {
    primario: '#4338ca',
    secundario: '#2563eb',
    acento: '#22d3ee',
    texto: '#ffffff',
    texto_suave: 'rgba(255,255,255,0.74)',
    fondo: '#eef2ff',
    rotulo_a: '#1b1764',
    rotulo_b: '#080c26',
    borde: 'rgba(255,255,255,0.18)',
    cursor: '#ffffff',
    onda: '#6366f1',
  },
  tipografia: {
    familia: '"Inter Variable",Inter,system-ui,-apple-system,"Segoe UI",sans-serif',
    titulo_px: 46,
    sub_px: 25,
    fuente_embebida: {
      activada: true,
      paquete: '@fontsource-variable/inter',
      fichero: 'files/inter-latin-wght-normal.woff2',
      nombre: 'Inter Variable',
    },
  },
  rotulo: {
    pos: 'bottom',
    radio_px: 24,
    opacidad: 0.9,
    sombra: true,
    blur_px: 22,
    margen_px: 56,
    ancho_max_px: 1180,
    contador: true,
    progreso: true,
    entrada_ms: 800,
    salida_ms: 380,
    escalonado_ms: 90,
  },
  cursor: { tamano: 30, color: null, onda_color: null, halo: true, halo_px: 48 },
  spotlight: { oscurecido: 0.58, radio_px: 18, margen_px: 14, ms: 520 },
  camara: { easing: 'cubic-bezier(.65,0,.35,1)', pan: 0.55, ms: 1000 },
  transicion: { fundido_ms: 450, color: null },
  intro: { segundos: 3, marca: 'CIE-10', titulo_px: 84, sub_px: 44 },
  cierre: {
    segundos: 3,
    linea1: 'Codificación clínica asistida por IA',
    linea2: 'Proyecto de fin de grado',
  },
  musica: { activada: true, volumen: 0.1, tonos: [110, 164.81, 220, 277.18] },
  viewport: { ancho: 1920, alto: 1080 },
};

const esObj = (x) => x && typeof x === 'object' && !Array.isArray(x);

export function mezclarTema(base, extra) {
  const out = { ...base };
  for (const [k, v] of Object.entries(extra || {})) {
    out[k] = esObj(v) && esObj(base?.[k]) ? mezclarTema(base[k], v) : v;
  }
  return out;
}

let TEMA = TEMA_DEFECTO;
export function setTema(extra = {}) {
  TEMA = mezclarTema(TEMA_DEFECTO, extra);
  if (TEMA.rotulo.posicion) TEMA = { ...TEMA, rotulo: { ...TEMA.rotulo, pos: TEMA.rotulo.posicion } };
  ANCHO = Number(TEMA.viewport.ancho ?? TEMA.viewport.width) || 1920;
  ALTO = Number(TEMA.viewport.alto ?? TEMA.viewport.height) || 1080;
  return TEMA;
}

export async function cargarPlaywright() {
  try {
    return await import('playwright');
  } catch {
    const raices = [
      process.env.PW_MODULES,
      '/tmp/pw/node_modules',
      '/usr/lib/node_modules',
      '/usr/local/lib/node_modules',
      '/work/node_modules',
    ].filter(Boolean);
    for (const r of raices) {
      try {
        return createRequire(path.join(r, 'x.js'))('playwright');
      } catch {}
    }
    throw new Error('No encuentro el paquete playwright (npm i playwright@1.56.1)');
  }
}

function capaEnPagina(t) {
  if (window.__demo) return;
  if (location.href === 'about:blank') {
    if (document.documentElement) document.documentElement.style.background = t.colores.fondo;
    return;
  }
  window.__demo = true;
  const c = t.colores;
  const ty = t.tipografia;
  const r = t.rotulo;
  const cu = t.cursor;
  const sp = t.spotlight;
  const tr = t.transicion;
  const cursorColor = cu.color || c.cursor;
  const ondaColor = cu.onda_color || c.onda;
  const tam = Number(cu.tamano) || 30;
  const op = Math.round(Number(r.opacidad) * 100);
  const sombra =
    r.sombra === true
      ? '0 32px 80px -24px rgba(2,6,23,.62),0 10px 30px -10px rgba(2,6,23,.38)'
      : r.sombra
        ? String(r.sombra)
        : 'none';
  const fuente = t._fuente
    ? `@font-face{font-family:"${t._fuente.nombre}";src:url(data:font/woff2;base64,${t._fuente.b64}) format("woff2");font-weight:100 900;font-style:normal;font-display:block}`
    : '';
  const haloOn = cu.halo !== false;
  const css = document.createElement('style');
  css.textContent = `
    ${fuente}
    :root{--d-acento:${c.acento};--d-texto:${c.texto};--d-suave:${c.texto_suave};--d-borde:${c.borde};
      --d-rotulo-a:${c.rotulo_a};--d-rotulo-b:${c.rotulo_b};--d-onda:${ondaColor};
      --d-fuente:${ty.familia};--d-titulo-px:${ty.titulo_px}px;--d-sub-px:${ty.sub_px}px;
      --d-radio:${r.radio_px}px;--d-opacidad:${op}%;--d-sombra:${sombra};--d-blur:${r.blur_px}px;
      --d-margen:${r.margen_px}px;--d-ancho:${r.ancho_max_px}px;
      --d-entrada:${r.entrada_ms}ms;--d-salida:${r.salida_ms}ms;--d-escalon:${r.escalonado_ms}ms;
      --d-cursor-px:${tam}px;--d-halo-px:${cu.halo_px || 48}px;
      --d-oscuro:${sp.oscurecido};--d-spot-radio:${sp.radio_px}px;--d-spot-ms:${sp.ms}ms}

    #__cursor{position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;transform-origin:0 0;
      filter:drop-shadow(0 5px 9px rgba(2,6,23,.34)) drop-shadow(0 1px 1px rgba(2,6,23,.45));
      transition:scale .12s ease-out}
    #__cursor.down{scale:.86}
    #__halo{position:fixed;left:0;top:0;z-index:2147483646;pointer-events:none;
      width:var(--d-halo-px);height:var(--d-halo-px);margin:calc(var(--d-halo-px)/-2) 0 0 calc(var(--d-halo-px)/-2);
      border-radius:50%;
      background:radial-gradient(circle,color-mix(in srgb,var(--d-onda) 30%,transparent) 0%,
        color-mix(in srgb,var(--d-onda) 12%,transparent) 55%,transparent 72%);
      border:1.5px solid color-mix(in srgb,var(--d-onda) 42%,transparent);
      transition:translate .1s ease-out,scale .12s ease-out}
    #__halo.down{scale:.7}
    .__onda{position:fixed;z-index:2147483646;pointer-events:none;width:24px;height:24px;margin:-12px 0 0 -12px;
      border-radius:50%;border:2px solid color-mix(in srgb,var(--d-onda) 80%,transparent);
      animation:__onda .6s cubic-bezier(.2,.7,.3,1) forwards}
    @keyframes __onda{from{transform:scale(.4);opacity:.8}to{transform:scale(3.2);opacity:0}}

    #__rotulo{position:fixed;z-index:2147483645;pointer-events:none;max-width:var(--d-ancho);
      font-family:var(--d-fuente);color:var(--d-texto);
      opacity:0;transform:translateY(30px) scale(.965);transform-origin:50% 100%;
      transition:opacity var(--d-salida) ease,transform var(--d-salida) cubic-bezier(.4,0,.2,1)}
    #__rotulo.on{opacity:1;transform:none;
      transition:opacity calc(var(--d-entrada)*.5) ease,transform var(--d-entrada) cubic-bezier(.34,1.5,.64,1)}
    #__rotulo.bottom{left:50%;bottom:var(--d-margen);translate:-50% 0}
    #__rotulo.top{left:50%;top:var(--d-margen);translate:-50% 0}
    #__rotulo.center{left:50%;top:50%;translate:-50% -50%;text-align:center}
    #__rotulo.bottom-left{left:var(--d-margen);bottom:var(--d-margen)}
    #__rotulo.bottom-right{right:var(--d-margen);bottom:var(--d-margen)}
    #__rotulo.top-left{left:var(--d-margen);top:var(--d-margen)}
    #__rotulo.top-right{right:var(--d-margen);top:var(--d-margen)}
    #__rotulo.top:not(.on),#__rotulo.top-left:not(.on),#__rotulo.top-right:not(.on){
      transform:translateY(-30px) scale(.965);transform-origin:50% 0}
    #__rotulo .__card{position:relative;overflow:hidden;padding:26px 42px 30px;border-radius:var(--d-radio);
      background:linear-gradient(135deg,color-mix(in srgb,var(--d-rotulo-a) var(--d-opacidad),transparent),
        color-mix(in srgb,var(--d-rotulo-b) var(--d-opacidad),transparent));
      -webkit-backdrop-filter:blur(var(--d-blur)) saturate(1.6);backdrop-filter:blur(var(--d-blur)) saturate(1.6);
      border:1px solid var(--d-borde);box-shadow:var(--d-sombra),inset 0 1px 0 rgba(255,255,255,.2)}
    #__rotulo .__card::before{content:"";position:absolute;left:-18%;top:-70%;width:75%;height:150%;
      background:radial-gradient(closest-side,color-mix(in srgb,var(--d-acento) 26%,transparent),transparent);
      pointer-events:none}
    #__rotulo .__card::after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;
      background:linear-gradient(180deg,rgba(255,255,255,.11),rgba(255,255,255,0) 42%)}
    #__rotulo .__card>*{position:relative;z-index:1}
    #__rotulo .__card>.__barra{position:absolute}
    #__rotulo.center .__card{padding:40px 64px 44px}
    #__rotulo .__chip{display:inline-flex;align-items:center;gap:11px;font-size:15px;font-weight:650;
      letter-spacing:.17em;text-transform:uppercase;color:var(--d-suave);font-variant-numeric:tabular-nums}
    #__rotulo .__chip i{width:8px;height:8px;border-radius:50%;background:var(--d-acento);
      box-shadow:0 0 14px 1px var(--d-acento)}
    #__rotulo .__chip em{font-style:normal}
    #__rotulo .__t{display:block;font-size:var(--d-titulo-px);line-height:1.08;font-weight:700;
      letter-spacing:-.03em;font-feature-settings:"cv11","ss03"}
    #__rotulo.center .__t{font-size:calc(var(--d-titulo-px)*1.3)}
    #__rotulo .__chip+.__t{margin-top:13px}
    #__rotulo .__sub{display:block;margin-top:11px;font-size:var(--d-sub-px);line-height:1.35;font-weight:450;
      letter-spacing:-.008em;color:var(--d-suave)}
    #__rotulo .__chip,#__rotulo .__t,#__rotulo .__sub{opacity:0;transform:translateY(16px);filter:blur(8px);
      transition:opacity .35s ease,transform .45s ease,filter .35s ease}
    #__rotulo.on .__chip,#__rotulo.on .__t,#__rotulo.on .__sub{opacity:1;transform:none;filter:none;
      transition:opacity .55s ease,transform .8s cubic-bezier(.2,.9,.2,1),filter .55s ease}
    #__rotulo.on .__chip{transition-delay:calc(var(--d-escalon)*.5)}
    #__rotulo.on .__t{transition-delay:calc(var(--d-escalon)*1.2)}
    #__rotulo.on .__sub{transition-delay:calc(var(--d-escalon)*2.2)}
    #__rotulo .__barra{position:absolute;left:0;right:0;bottom:0;height:3px;background:rgba(255,255,255,.09)}
    #__rotulo .__barra i{display:block;height:100%;width:0;border-radius:0 3px 3px 0;
      background:linear-gradient(90deg,var(--d-acento),color-mix(in srgb,var(--d-acento) 35%,#fff));
      box-shadow:0 0 14px var(--d-acento);transition:width 1.1s cubic-bezier(.2,.8,.2,1) .3s}
    #__rotulo.on .__barra i{width:var(--p,0%)}

    #__zona{position:fixed;z-index:2147483644;pointer-events:none;border-radius:var(--d-spot-radio);
      box-shadow:0 0 0 100vmax rgba(4,7,20,var(--d-oscuro)),
        0 0 0 2px color-mix(in srgb,var(--d-acento) 90%,transparent),
        0 0 44px 6px color-mix(in srgb,var(--d-acento) 36%,transparent);
      opacity:0;transition:opacity calc(var(--d-spot-ms)*.8) ease,left var(--d-spot-ms) cubic-bezier(.65,0,.35,1),
        top var(--d-spot-ms) cubic-bezier(.65,0,.35,1),width var(--d-spot-ms) cubic-bezier(.65,0,.35,1),
        height var(--d-spot-ms) cubic-bezier(.65,0,.35,1)}
    #__zona.on{opacity:1;animation:__latido 2.6s ease-in-out infinite}
    @keyframes __latido{50%{box-shadow:0 0 0 100vmax rgba(4,7,20,var(--d-oscuro)),
      0 0 0 2px color-mix(in srgb,var(--d-acento) 100%,transparent),
      0 0 64px 12px color-mix(in srgb,var(--d-acento) 46%,transparent)}}

    #__fundido{position:fixed;inset:0;z-index:2147483640;pointer-events:none;
      background:${tr.color || c.fondo};opacity:1;animation:__fund ${Number(tr.fundido_ms) || 0}ms .04s ease-out forwards}
    @keyframes __fund{to{opacity:0}}
  `;
  const montar = () => {
    document.documentElement.appendChild(css);
    if (Number(tr.fundido_ms) > 0) {
      const f = document.createElement('div');
      f.id = '__fundido';
      document.documentElement.appendChild(f);
      setTimeout(() => f.remove(), Number(tr.fundido_ms) + 300);
    }
    let halo = null;
    if (haloOn) {
      halo = document.createElement('div');
      halo.id = '__halo';
      document.documentElement.appendChild(halo);
    }
    const el = document.createElement('div');
    el.id = '__cursor';
    el.innerHTML = `<svg viewBox="0 0 24 24" width="${tam}" height="${tam}" style="display:block;margin:${(-2 / 24) * tam}px 0 0 ${(-4 / 24) * tam}px"><path d="M4 2l15 9.2-6.6 1.6 3.6 6.9-2.9 1.5-3.6-6.9L4.6 18z" fill="${cursorColor}" stroke="#0f172a" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
    document.documentElement.appendChild(el);
    let p = null;
    try {
      p = JSON.parse(sessionStorage.getItem('__cur') || 'null');
    } catch {}
    const poner = (x, y) => {
      el.style.translate = `${x}px ${y}px`;
      if (halo) halo.style.translate = `${x}px ${y}px`;
    };
    poner(p ? p.x : 960, p ? p.y : 600);
    addEventListener(
      'mousemove',
      (e) => {
        poner(e.clientX, e.clientY);
        try {
          sessionStorage.setItem('__cur', JSON.stringify({ x: e.clientX, y: e.clientY }));
        } catch {}
      },
      true,
    );
    addEventListener(
      'mousedown',
      (e) => {
        el.classList.add('down');
        halo?.classList.add('down');
        const o = document.createElement('div');
        o.className = '__onda';
        o.style.left = e.clientX + 'px';
        o.style.top = e.clientY + 'px';
        document.documentElement.appendChild(o);
        setTimeout(() => o.remove(), 700);
      },
      true,
    );
    addEventListener(
      'mouseup',
      () => {
        el.classList.remove('down');
        halo?.classList.remove('down');
      },
      true,
    );
  };
  if (document.documentElement) montar();
  else document.addEventListener('DOMContentLoaded', montar);
}

function cargarFuente(tema) {
  const f = tema.tipografia?.fuente_embebida;
  if (!f || f.activada === false) return null;
  const raiz = process.env.PW_MODULES || '/tmp/pw/node_modules';
  const fichero = path.join(raiz, f.paquete, f.fichero);
  try {
    if (!fs.existsSync(fichero)) {
      execFileSync('npm', ['i', '--prefix', path.dirname(raiz), '--no-audit', '--no-fund', f.paquete], {
        stdio: 'ignore',
        timeout: 120000,
      });
    }
    return { nombre: f.nombre, b64: fs.readFileSync(fichero).toString('base64') };
  } catch (e) {
    console.log(`[aviso] sin tipografía embebida (${String(e).split('\n')[0]}): uso la del sistema`);
    return null;
  }
}

export async function abrir(id, opciones = {}) {
  if (opciones.tema) setTema(opciones.tema);
  if (opciones.ritmo != null) setRitmo(opciones.ritmo);
  const pw = await cargarPlaywright();
  const base = opciones.base || BASE_URL;
  const args = ['--hide-scrollbars', '--force-device-scale-factor=1'];
  if (/\/\/localhost[:/]/.test(base) || base === 'http://localhost') {
    args.push('--host-resolver-rules=MAP localhost host.docker.internal');
  }
  const browser = await pw.chromium.launch({ args });
  const tmp = path.join(OUT, 'clips', `.tmp-${id}`);
  fs.rmSync(tmp, { recursive: true, force: true });
  fs.mkdirSync(tmp, { recursive: true });
  const context = await browser.newContext({
    viewport: { width: ANCHO, height: ALTO },
    screen: { width: ANCHO, height: ALTO },
    deviceScaleFactor: 1,
    locale: opciones.locale || 'es-ES',
    recordVideo: { dir: tmp, size: { width: ANCHO, height: ALTO } },
  });
  await context.addInitScript(capaEnPagina, { ...TEMA, _fuente: cargarFuente(TEMA) });
  await context.addInitScript(() => {
    try {
      localStorage.setItem('cie10_locale', 'es');
    } catch {}
  });
  const page = await context.newPage();
  page.on('pageerror', (e) => console.log(`[js] ${e}`));
  await page.goto('about:blank').catch(() => {});
  return { id, pw, browser, context, page, base, tmp, nCaptura: 0, tema: TEMA, ritmo: RITMO };
}

export async function cerrar(v) {
  const video = v.page.video();
  await v.context.close();
  const destino = path.join(OUT, 'clips', `${v.id}.webm`);
  if (video) {
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    await video.saveAs(destino);
  }
  await v.browser.close();
  fs.rmSync(v.tmp, { recursive: true, force: true });
  console.log(`clip: ${destino}`);
  return destino;
}

export async function captura(v, nombre) {
  const dir = path.join(OUT, 'screenshots', v.id);
  fs.mkdirSync(dir, { recursive: true });
  v.nCaptura += 1;
  const f = path.join(dir, `${String(v.nCaptura).padStart(2, '0')}-${nombre}.png`);
  await v.page.screenshot({ path: f });
  return f;
}

let CAP = 0;
let CAP_TOTAL = 0;
export function setCapitulos(total) {
  CAP_TOTAL = Math.max(0, Number(total) || 0);
  CAP = 0;
}

export async function rotulo(page, titulo, subtitulo = '', { ms = 3200, pos, contador } = {}) {
  const lugar = pos || TEMA.rotulo.pos || 'bottom';
  const conContador = (contador ?? TEMA.rotulo.contador) !== false && CAP_TOTAL > 0;
  if (conContador) CAP = Math.min(CAP + 1, CAP_TOTAL);
  const barra = TEMA.rotulo.progreso !== false && conContador;
  const fuente = TEMA.tipografia.fuente_embebida?.nombre;
  if (fuente) await page.evaluate((f) => document.fonts?.load(`700 40px "${f}"`), fuente).catch(() => {});
  await page.evaluate(
    ([t, s, p, i, n, b]) => {
      let el = document.getElementById('__rotulo');
      if (!el) {
        el = document.createElement('div');
        el.id = '__rotulo';
        document.documentElement.appendChild(el);
      }
      el.className = p;
      el.style.setProperty('--p', n ? ((i / n) * 100).toFixed(1) + '%' : '0%');
      const dos = (x) => String(x).padStart(2, '0');
      el.innerHTML =
        '<div class="__card">' +
        (i && n ? `<span class="__chip"><i></i><em>${dos(i)} / ${dos(n)}</em></span>` : '') +
        '<b class="__t"></b>' +
        (s ? '<span class="__sub"></span>' : '') +
        (b ? '<div class="__barra"><i></i></div>' : '') +
        '</div>';
      el.querySelector('.__t').textContent = t;
      if (s) el.querySelector('.__sub').textContent = s;
      requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('on')));
    },
    [titulo, subtitulo, lugar, conContador ? CAP : 0, CAP_TOTAL, barra],
  );
  if (ms > 0) {
    await pausa(ms);
    await quitarRotulo(page);
  }
}

export async function quitarRotulo(page) {
  await page.evaluate(() => document.getElementById('__rotulo')?.classList.remove('on'));
  await pausaFija(Math.max(350, Number(TEMA.rotulo.salida_ms) || 380));
}

export async function resaltar(page, loc, { ms = 2200, margen } = {}) {
  const m = margen ?? TEMA.spotlight.margen_px ?? 14;
  const caja = await loc.boundingBox();
  if (!caja) return;
  await page.evaluate(
    ([c, mg]) => {
      let z = document.getElementById('__zona');
      if (!z) {
        z = document.createElement('div');
        z.id = '__zona';
        document.documentElement.appendChild(z);
      }
      const poner = () => {
        z.style.left = c.x - mg + 'px';
        z.style.top = c.y - mg + 'px';
        z.style.width = c.width + 2 * mg + 'px';
        z.style.height = c.height + 2 * mg + 'px';
      };
      if (z.classList.contains('on')) poner();
      else {
        z.style.transition = 'none';
        poner();
        void z.offsetWidth;
        z.style.transition = '';
      }
      requestAnimationFrame(() => z.classList.add('on'));
    },
    [caja, m],
  );
  await pausa(ms);
  await page.evaluate(() => document.getElementById('__zona')?.classList.remove('on'));
  await pausaFija(Math.round((Number(TEMA.spotlight.ms) || 520) * 0.9));
}

let ultimaPos = { x: 960, y: 600 };
let signoCurva = 1;
const ease = (t) => t * t * t * (t * (t * 6 - 15) + 10);

export async function moverA(page, x, y, ms = 750) {
  const { x: x0, y: y0 } = ultimaPos;
  const dist = Math.hypot(x - x0, y - y0);
  const dur = ms * Math.min(1.35, Math.max(0.7, 0.7 + dist / 2200));
  const pasos = Math.max(14, Math.round((dur * RITMO) / 16));
  signoCurva = -signoCurva;
  const k = 0.11 * signoCurva;
  const cx = (x0 + x) / 2 + (y - y0) * k;
  const cy = (y0 + y) / 2 - (x - x0) * k;
  for (let i = 1; i <= pasos; i++) {
    const t = ease(i / pasos);
    const px = (1 - t) * (1 - t) * x0 + 2 * (1 - t) * t * cx + t * t * x;
    const py = (1 - t) * (1 - t) * y0 + 2 * (1 - t) * t * cy + t * t * y;
    await page.mouse.move(px, py);
    await pausaFija((dur * RITMO) / pasos);
  }
  ultimaPos = { x, y };
}

async function centro(loc) {
  await loc.scrollIntoViewIfNeeded();
  const c = await loc.boundingBox();
  if (!c) throw new Error('elemento sin caja visible');
  return { x: c.x + c.width / 2, y: c.y + c.height / 2 };
}

export async function mover(page, loc, ms = 750) {
  const { x, y } = await centro(loc);
  await moverA(page, x, y, ms);
}

export async function clic(page, loc, { ms = 700, despues = 450 } = {}) {
  await mover(page, loc, ms);
  const { x, y } = await centro(loc);
  if (Math.hypot(x - ultimaPos.x, y - ultimaPos.y) > 3) await moverA(page, x, y, 220);
  await pausaFija(160);
  await page.mouse.down();
  await pausaFija(110);
  await page.mouse.up();
  await pausa(despues);
}

export async function teclear(page, loc, texto, { retardo = 55, despues = 400 } = {}) {
  await clic(page, loc, { despues: 200 });
  await page.keyboard.type(texto, { delay: Math.round(retardo * RITMO) });
  await pausa(despues);
}

export async function zoom(page, loc = null, escala = 1.35, ms, opciones = {}) {
  const cam = TEMA.camara || {};
  const d = Math.max(250, Math.round((ms ?? cam.ms ?? 1000) * RITMO));
  const easing = cam.easing || 'cubic-bezier(.65,0,.35,1)';
  if (!loc) {
    await page.evaluate(
      ([dur, ez]) => {
        document.body.style.transition = `transform ${dur}ms ${ez}`;
        document.body.style.transform = 'none';
      },
      [d, easing],
    );
    await pausaFija(d + 120);
    return;
  }
  const pan = Math.min(1, Math.max(0, Number(opciones.pan ?? cam.pan ?? 0.55)));
  await loc.evaluate(
    (el, [e, dur, ez, pn]) => {
      const b = document.body;
      const antes = b.style.transform;
      b.style.transition = 'none';
      b.style.transform = 'none';
      const r = el.getBoundingClientRect();
      const sx = window.scrollX;
      const sy = window.scrollY;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const px = r.left + r.width / 2;
      const py = r.top + r.height / 2;
      const ox = px + (vw / 2 - px) * pn;
      const oy = py + (vh / 2 - py) * pn;
      const docW = Math.max(document.documentElement.scrollWidth, vw);
      const docH = Math.max(document.documentElement.scrollHeight, vh);
      const lim = (v, min, max) => Math.min(max, Math.max(min, v));
      const tx = lim(ox + sx - e * (px + sx), vw + sx - e * docW, sx);
      const ty = lim(oy + sy - e * (py + sy), vh + sy - e * docH, sy);
      b.style.transformOrigin = '0 0';
      b.style.transform = antes && antes !== 'none' ? antes : 'none';
      void b.offsetWidth;
      b.style.transition = `transform ${dur}ms ${ez}`;
      b.style.transform = `translate(${tx}px,${ty}px) scale(${e})`;
    },
    [escala, d, easing, pan],
  );
  await pausaFija(d + 120);
}

export function datosCuenta() {
  const sufijo = Math.random().toString(36).slice(2, 10);
  return {
    first_name: 'Laura',
    last_name: 'Martín Gil',
    username: `dra_martin_${sufijo}`,
    email: `demo_${sufijo}@ejemplo.test`,
    password: 'PruebaSegura1!',
  };
}

export async function confirmarCorreo(v, cuenta) {
  const enlace = await enlaceConfirmacion(cuenta.email);
  await v.page.goto(enlace.replace(/^https?:\/\/[^/]+/, v.base), { waitUntil: 'load' });
  await v.page.getByRole('button', { name: rx('cerrar sesión') }).waitFor({ timeout: 30000 });
}

export async function cuentaDemo(v, { nueva = false } = {}) {
  if (!nueva && process.env.DEMO_EMAIL && process.env.DEMO_PASSWORD) {
    return { email: process.env.DEMO_EMAIL, password: process.env.DEMO_PASSWORD };
  }
  const datos = datosCuenta();
  const args = v.base.includes('localhost')
    ? ['--host-resolver-rules=MAP localhost host.docker.internal']
    : [];
  const br = await v.pw.chromium.launch({ args });
  const ctx = await br.newContext({ viewport: { width: 1280, height: 900 }, locale: 'es-ES' });
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('cie10_locale', 'es');
    } catch {}
  });
  const p = await ctx.newPage();
  await p.goto(v.base + '/', { waitUntil: 'load' });
  await p.getByRole('button', { name: rx('^(registr|sign up|crear)') }).first().click();
  await p.getByPlaceholder('Juan').fill(datos.first_name);
  await p.getByPlaceholder('García López').fill(datos.last_name);
  await p.getByPlaceholder('dr_garcia').fill(datos.username);
  await p.locator('input[type="email"]').fill(datos.email);
  await p.locator('input[type="password"]').fill(datos.password);
  await p.locator('button[type="submit"]').click();
  const enlace = await enlaceConfirmacion(datos.email);
  await p.goto(enlace.replace(/^https?:\/\/[^/]+/, v.base), { waitUntil: 'load' });
  await p.getByRole('button', { name: rx('cerrar sesión') }).waitFor({ timeout: 30000 });
  await br.close();
  return { email: datos.email, password: datos.password };
}

async function enlaceConfirmacion(email, espera = 30000) {
  const limite = Date.now() + espera;
  while (Date.now() < limite) {
    try {
      const b = await (
        await fetch(`${MAILPIT_URL}/api/v1/search?query=${encodeURIComponent('to:' + email)}`)
      ).json();
      if (b.messages?.length) {
        const m = await (await fetch(`${MAILPIT_URL}/api/v1/message/${b.messages[0].ID}`)).json();
        const r = /https?:\/\/\S+\/confirm-email\?token=[\w.-]+/.exec(m.Text || '');
        if (r) return r[0];
      }
    } catch {}
    await pausaFija(500);
  }
  throw new Error(`No llegó el correo de confirmación a ${email}`);
}

export async function iniciarSesion(v, cuenta, { lento = true } = {}) {
  const { page } = v;
  await page.goto(v.base + '/', { waitUntil: 'load' });
  const email = page.locator('input[type="email"]');
  const pass = page.locator('input[type="password"]');
  if (lento) {
    await teclear(page, email, cuenta.email, { retardo: 45 });
    await teclear(page, pass, cuenta.password, { retardo: 70 });
    await clic(page, page.locator('button[type="submit"]'));
  } else {
    await email.fill(cuenta.email);
    await pass.fill(cuenta.password);
    await page.locator('button[type="submit"]').click();
  }
  await page.getByRole('button', { name: rx('cerrar sesión') }).waitFor({ timeout: 30000 });
}

