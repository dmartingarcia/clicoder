import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import * as lib from './lib.mjs';

const GUIONES = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../guiones');
const { parse } = createRequire(path.join(process.env.PW_MODULES || '/tmp/pw/node_modules', 'x.js'))('yaml');

const argv = process.argv.slice(2);
const soloValidar = argv.includes('--validar');
const destino = argv.find((a) => !a.startsWith('--'));
if (!destino) {
  console.error('Uso: node runner.mjs [--validar] NN | ruta/guion.yml');
  process.exit(2);
}
const fichero = /\.ya?ml$/.test(destino) ? path.resolve(destino) : path.join(GUIONES, `${destino}.yml`);
const dirGuion = path.dirname(fichero);

const ACCIONES = new Set([
  'rotulo', 'quitar_rotulo', 'clic', 'teclear', 'mover', 'zoom', 'resaltar', 'pausa',
  'esperar', 'ir', 'tecla', 'scroll', 'captura', 'js', 'login', 'confirmar',
]);
const META = new Set(['seguro', 'nota', 'timeout']);
const CLAVES_ACCION = {
  rotulo: ['titulo', 'sub', 'ms', 'pos', 'posicion'],
  clic: ['en', 'ms', 'despues'],
  teclear: ['en', 'texto', 'retardo', 'despues'],
  mover: ['en', 'ms'],
  zoom: ['en', 'escala', 'ms', 'reset'],
  resaltar: ['en', 'ms', 'margen'],
  esperar: ['texto', 'selector', 'max'],
  ir: ['url'],
  scroll: ['en', 'y', 'ms'],
  captura: ['nombre'],
  js: ['modulo', 'args'],
  login: ['lento'],
  confirmar: [],
};
const CLAVES_RAIZ = new Set(['id', 'titulo', 'subtitulo', 'ritmo', 'velocidad', 'cuenta', 'textos', 'tema', 'pasos']);

const esObj = (x) => x && typeof x === 'object' && !Array.isArray(x);
const comoObj = (x, clave) => (esObj(x) ? x : { [clave]: x });
const esc = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const accionDe = (paso) => {
  const claves = Object.keys(paso).filter((k) => !META.has(k));
  return claves.length === 1 ? claves[0] : null;
};
const expandirEnv = (s) =>
  String(s).replace(/\$\{(\w+)(?::-([^}]*))?\}/g, (_, n, def) => process.env[n] || def || '');

const pareceRuta = (s) =>
  typeof s === 'string' && !/\s/.test(s) && (/^\.{1,2}\//.test(s) || /^textos\//.test(s) || /\.(txt|md)$/.test(s));

function cargarTextos(textos, errores) {
  const out = {};
  for (const [k, val] of Object.entries(textos || {})) {
    if (!pareceRuta(val)) {
      out[k] = String(val).trimEnd();
      continue;
    }
    const f = path.resolve(dirGuion, val);
    if (fs.existsSync(f)) out[k] = fs.readFileSync(f, 'utf8').trimEnd();
    else errores.push(`textos.${k}: no existe ${val}`);
  }
  return out;
}

function resolver(x, vars) {
  if (typeof x === 'string') {
    const m = /^@(\w+)$/.exec(x);
    return m && m[1] in vars ? vars[m[1]] : x;
  }
  if (Array.isArray(x)) return x.map((i) => resolver(i, vars));
  if (esObj(x)) return Object.fromEntries(Object.entries(x).map(([k, val]) => [k, resolver(val, vars)]));
  return x;
}

function primero(page, t) {
  if (t.startsWith('rol=')) {
    const m = /^rol=([\w-]+)(?:\[name=(.+)\])?$/s.exec(t);
    if (!m) throw new Error(`selector rol= no válido: ${t}`);
    let nombre;
    if (m[2]) {
      const r = /^\/(.*)\/([a-z]*)$/s.exec(m[2]);
      nombre = r ? new RegExp(r[1], r[2]) : m[2].replace(/^["']|["']$/g, '');
    }
    return page.getByRole(m[1], nombre ? { name: nombre } : {});
  }
  if (t.startsWith('texto=')) return page.getByText(new RegExp(esc(t.slice(6)), 'i'));
  return page.locator(t);
}

function loc(page, sel) {
  if (typeof sel !== 'string' || !sel.trim()) throw new Error('selector vacío');
  const [inicio, ...resto] = sel.trim().split(/\s+>>\s+/);
  let l = primero(page, inicio);
  for (const p of resto) {
    const n = /^nth=(-?\d+)$/.exec(p);
    if (n) l = l.nth(Number(n[1]));
    else if (p === 'first') l = l.first();
    else if (p === 'last') l = l.last();
    else l = l.locator(p);
  }
  return l.first();
}

function validar(guion, vars, errores) {
  for (const k of Object.keys(guion)) {
    if (!CLAVES_RAIZ.has(k)) console.log(`clave desconocida en la raíz: ${k}`);
  }
  if (!Array.isArray(guion.pasos) || guion.pasos.length === 0) errores.push('pasos: falta o está vacío');
  (guion.pasos || []).forEach((p, i) => {
    const n = i + 1;
    if (!esObj(p)) return errores.push(`paso ${n}: debe ser un objeto`);
    const ac = accionDe(p);
    if (!ac) return errores.push(`paso ${n}: debe tener exactamente una acción (${Object.keys(p).join(', ')})`);
    if (!ACCIONES.has(ac)) return errores.push(`paso ${n}: acción desconocida "${ac}"`);
    const a = p[ac];
    const o = comoObj(a, 'x');
    if (esObj(a) && CLAVES_ACCION[ac]) {
      const raras = Object.keys(a).filter((k) => !CLAVES_ACCION[ac].includes(k));
      if (raras.length) errores.push(`paso ${n} ${ac}: clave(s) desconocida(s) "${raras.join('", "')}" (¿una coma sin comillas?)`);
    }
    if (['clic', 'mover', 'resaltar'].includes(ac) && !(typeof a === 'string' || o.en)) errores.push(`paso ${n} ${ac}: falta el selector`);
    if (ac === 'teclear' && !(esObj(a) && a.en && a.texto != null)) errores.push(`paso ${n} teclear: faltan en y texto`);
    if (ac === 'esperar' && !(typeof a === 'string' || o.texto || o.selector)) errores.push(`paso ${n} esperar: falta texto o selector`);
    if (ac === 'ir' && !(typeof a === 'string' || o.url)) errores.push(`paso ${n} ir: falta la url`);
    if (ac === 'rotulo' && !(typeof a === 'string' || o.titulo)) errores.push(`paso ${n} rotulo: falta el titulo`);
    if (ac === 'js') {
      if (!esObj(a) || !a.modulo) errores.push(`paso ${n} js: falta modulo`);
      else if (!fs.existsSync(path.resolve(dirGuion, a.modulo))) errores.push(`paso ${n} js: no existe ${a.modulo}`);
    }
    for (const r of JSON.stringify(a ?? '').match(/"@(\w+)"/g) || []) {
      const nombre = r.slice(2, -1);
      if (!(nombre in vars)) errores.push(`paso ${n}: ${r} no está en textos`);
    }
  });
}

async function ejecutar(v, accion, a, ctx) {
  const { page } = v;
  switch (accion) {
    case 'rotulo': {
      const o = comoObj(a, 'titulo');
      await lib.rotulo(page, o.titulo ?? '', o.sub ?? '', { ms: o.ms ?? 3200, pos: o.pos ?? o.posicion });
      break;
    }
    case 'quitar_rotulo':
      await lib.quitarRotulo(page);
      break;
    case 'clic': {
      const o = comoObj(a, 'en');
      await lib.clic(page, loc(page, o.en), { ms: o.ms ?? 700, despues: o.despues ?? 450 });
      break;
    }
    case 'teclear':
      await lib.teclear(page, loc(page, a.en), String(a.texto), { retardo: a.retardo ?? 30, despues: a.despues ?? 400 });
      break;
    case 'mover': {
      const o = comoObj(a, 'en');
      await lib.mover(page, loc(page, o.en), o.ms ?? 750);
      break;
    }
    case 'zoom': {
      if (a == null || a.reset) {
        await lib.zoom(page);
        break;
      }
      const o = comoObj(a, 'en');
      await lib.zoom(page, o.en ? loc(page, o.en) : null, o.escala ?? 1.35, o.ms ?? 900);
      break;
    }
    case 'resaltar': {
      const o = comoObj(a, 'en');
      await lib.resaltar(page, loc(page, o.en), { ms: o.ms ?? 2200, margen: o.margen });
      break;
    }
    case 'pausa':
      await lib.pausa(Number(esObj(a) ? a.ms : a));
      break;
    case 'esperar': {
      const o = typeof a === 'string' ? { texto: a } : a;
      const l = o.selector ? loc(page, o.selector) : page.getByText(new RegExp(esc(o.texto), 'i')).first();
      await l.waitFor({ state: 'visible', timeout: (o.max ?? 60) * 1000 });
      break;
    }
    case 'ir': {
      const url = expandirEnv(comoObj(a, 'url').url);
      await page.goto(url.startsWith('/') ? v.base + url : url, { waitUntil: 'load' });
      break;
    }
    case 'tecla':
      await page.keyboard.press(String(esObj(a) ? a.nombre : a));
      await lib.pausa(300);
      break;
    case 'scroll': {
      const o = comoObj(a, 'en');
      if (o.en && o.y == null) {
        await loc(page, o.en).evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
      } else if (o.en) {
        await loc(page, o.en).evaluate((el, y) => el.scrollTo({ top: y, behavior: 'smooth' }), o.y);
      } else {
        await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'smooth' }), o.y ?? 0);
      }
      await lib.pausa(o.ms ?? 900);
      break;
    }
    case 'captura':
      await lib.captura(v, String(esObj(a) ? a.nombre : a));
      break;
    case 'js': {
      const mod = await import(pathToFileURL(path.resolve(dirGuion, a.modulo)).href);
      await mod.default(v, lib, a.args ?? {}, ctx);
      break;
    }
    case 'confirmar':
      await lib.confirmarCorreo(v, ctx.cuenta);
      break;
    case 'login':
      await lib.iniciarSesion(v, ctx.cuenta, { lento: esObj(a) ? (a.lento ?? true) : true });
      break;
  }
}

const resumen = (x) => {
  const s = typeof x === 'string' ? x : JSON.stringify(x ?? '');
  return s.length > 70 ? s.slice(0, 67) + '…' : s;
};
const segundos = (desde) => ((Date.now() - desde) / 1000).toFixed(1);
const sh = (s) => `'${String(s).replace(/'/g, `'\\''`)}'`;

async function main() {
  if (!fs.existsSync(fichero)) throw new Error(`No existe el guion ${fichero}`);
  const guion = parse(fs.readFileSync(fichero, 'utf8')) || {};
  const id = String(guion.id ?? path.basename(fichero, path.extname(fichero)));

  const errores = [];
  const textos = cargarTextos(guion.textos, errores);
  const vars = { ...textos, email: '(email)', password: '(password)', nombre: '(nombre)', apellidos: '(apellidos)', usuario: '(usuario)' };
  validar(guion, vars, errores);
  if (errores.length) {
    console.error(`Guion ${path.basename(fichero)} con errores:\n  - ${errores.join('\n  - ')}`);
    process.exit(1);
  }

  const ficheroTema = path.join(GUIONES, 'tema.yml');
  let temaGlobal = {};
  if (fs.existsSync(ficheroTema)) {
    const t = parse(fs.readFileSync(ficheroTema, 'utf8')) || {};
    temaGlobal = esObj(t.tema) ? t.tema : t;
  }
  const tema = lib.setTema(lib.mezclarTema(temaGlobal, guion.tema || {}));
  const ritmo = lib.setRitmo(guion.ritmo ?? 1);
  const pasos = guion.pasos;
  lib.setCapitulos(pasos.filter((p) => accionDe(p) === 'rotulo').length);

  if (soloValidar) {
    console.log(`OK ${path.basename(fichero)}: ${pasos.length} pasos, ritmo ${ritmo}, ` +
      `viewport ${lib.ANCHO}x${lib.ALTO}, textos: ${Object.keys(textos).join(', ') || '-'}`);
    return;
  }

  let cuenta = null;
  if (guion.cuenta === 'nueva') {
    cuenta = lib.datosCuenta();
    Object.assign(vars, {
      nombre: cuenta.first_name,
      apellidos: cuenta.last_name,
      usuario: cuenta.username,
      email: cuenta.email,
      password: cuenta.password,
    });
  } else if (guion.cuenta === 'demo' || guion.cuenta === 'registro') {
    const pw = await lib.cargarPlaywright();
    cuenta = await lib.cuentaDemo({ pw, base: lib.BASE_URL }, { nueva: guion.cuenta === 'registro' });
    vars.email = cuenta.email;
    vars.password = cuenta.password;
  }

  fs.rmSync(path.join(lib.OUT, 'screenshots', id), { recursive: true, force: true });
  const v = await lib.abrir(id, { tema, ritmo });
  const ctx = { cuenta, textos, vars };
  const t0 = Date.now();
  let fallo = null;
  try {
    for (let i = 0; i < pasos.length; i++) {
      const paso = pasos[i];
      const accion = accionDe(paso);
      const param = resolver(paso[accion], vars);
      const n = `${String(i + 1).padStart(2, '0')}/${pasos.length}`;
      const t = Date.now();
      v.page.setDefaultTimeout((paso.timeout ?? (paso.seguro ? 8 : 30)) * 1000);
      try {
        await ejecutar(v, accion, param, ctx);
        console.log(`[${n}] ${accion.padEnd(13)} ${segundos(t).padStart(5)} s  t=${segundos(t0).padStart(6)} s  ${resumen(param)}`);
      } catch (e) {
        const msg = String(e).split('\n')[0];
        await lib.captura(v, `fallo-${accion}-${i + 1}`).catch(() => {});
        if (!paso.seguro) {
          console.error(`[error] paso ${n} ${accion}: ${msg}`);
          fallo = e;
          break;
        }
        console.log(`[aviso] paso ${n} ${accion}: ${msg}`);
      }
    }
  } finally {
    console.log(`duración medida: ${segundos(t0)} s (ritmo ${ritmo})`);
    await lib.cerrar(v);
  }
  if (fallo) {
    process.exitCode = 1;
    return;
  }

  const env = {
    TITULO: guion.titulo ?? '',
    SUBTITULO: guion.subtitulo ?? '',
    COLOR_A: tema.colores.primario,
    COLOR_B: tema.colores.secundario,
    COLOR_TEXTO: tema.colores.texto,
    COLOR_FONDO: tema.colores.fondo,
    INTRO_S: tema.intro.segundos,
    CIERRE_S: tema.cierre.segundos,
    MARCA: tema.intro.marca,
    CIERRE_1: tema.cierre.linea1,
    CIERRE_2: tema.cierre.linea2,
    MUSICA: tema.musica.activada ? 1 : 0,
    MUSICA_VOL: tema.musica.volumen,
    MUSICA_TONOS: (tema.musica.tonos || []).join(','),
    VELOCIDAD: guion.velocidad ?? 1,
    COLOR_ACENTO: tema.colores.acento,
    INTRO_TITULO_PX: tema.intro.titulo_px,
    INTRO_SUB_PX: tema.intro.sub_px,
    RITMO: ritmo,
  };
  const destinoEnv = path.join(lib.OUT, 'clips', `${id}.env`);
  fs.mkdirSync(path.dirname(destinoEnv), { recursive: true });
  fs.writeFileSync(destinoEnv, Object.entries(env).map(([k, val]) => `${k}=${sh(val)}`).join('\n') + '\n');
  console.log(`parámetros de montaje: ${destinoEnv}`);
}

main().catch((e) => {
  console.error(String(e?.stack || e));
  process.exit(1);
});
