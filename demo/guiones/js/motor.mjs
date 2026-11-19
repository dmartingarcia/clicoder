import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(aqui, '../../..');
const PAGINA = path.join(RAIZ, 'demo/capturas/paginas/motor.html');
const leer = (f) => fs.readFileSync(path.join(RAIZ, f), 'utf8');
const json = (f) => JSON.parse(leer(f));
const num = (s) => Number(s.replace(/\./g, '').replace(',', '.'));
const NUMEROS = { cinco: 5, diez: 10 };

function buscar(texto, re, fichero) {
  const m = re.exec(texto);
  if (!m) throw new Error(`motor.mjs: ${re} no aparece en ${fichero}`);
  return m;
}

function memoria() {
  const f = {
    intro: 'tfg/Caps/1_Introduccion.tex',
    objetivo: 'tfg/Caps/2_Objetivo.tex',
    plan: 'tfg/Caps/3_Planificacion.tex',
    conclusiones: 'tfg/Caps/5_Conclusiones.tex',
  };
  const t = Object.fromEntries(Object.entries(f).map(([k, v]) => [k, leer(v)]));
  const [, codigos] = buscar(t.intro, /([\d.]+) códigos de diagnóstico/, f.intro);
  const [, media] = buscar(t.intro, /media de ([\d,]+) códigos de diagnóstico por informe/, f.intro);
  const [, minutos] = buscar(t.objetivo, /(\d+)~?minutos de media/, f.objetivo);
  const [, informes, objetivo] = buscar(
    t.conclusiones,
    /entrenado sobre (\d+) documentos con ([\d.]+) códigos objetivo/,
    f.conclusiones,
  );
  const [, candidatos, evaluados] = buscar(t.conclusiones, /de (\w+) modelos candidatos, (\w+) evaluados/, f.conclusiones);
  const [, pivotes] = buscar(t.plan, /tres pivotes \(([A-Z, ]+)\)/, f.plan);
  const [, porPivote] = buscar(t.plan, /cada pivote genera (\d+) paráfrasis/, f.plan);
  buscar(t.plan, /se descartó porque empeoró/, f.plan);
  return {
    codigos: num(codigos),
    media: num(media),
    minutos: num(minutos),
    informes: num(informes),
    objetivo: num(objetivo),
    candidatos: NUMEROS[candidatos],
    evaluados: NUMEROS[evaluados],
    aumento: { pivotes: pivotes.split(',').map((x) => x.trim()), porPivote: num(porPivote) },
  };
}

function motores() {
  const c = json('ai_engine/model/comparativa_motores.json');
  const par = (m) => ({ map: m.map_strict, f1: m.f1 });
  return { diccionario: par(c.diccionario), modelo: par(c.modelo_solo), fusion: par(c.modelo_fusion) };
}

const limpiar = (s) => s.replace(/\\([&%$#_{}])/g, '$1');

function explicacion() {
  const f = 'tfg/figs/ejemplo-explicabilidad.tex';
  const t = leer(f);
  const [, cuerpo] = buscar(t, /\\baselineskip\}\{13pt\}\s*([\s\S]*?)\s*\}\}\s*\\caption/, f);
  const [, codigo, descripcion] = buscar(t, /\\texttt\{([A-Z0-9.]+)\} \(([^)]*)\)/, f);
  const palabras = [];
  let i = 0;
  for (const m of cuerpo.matchAll(/\\colorbox\{amarillo!(\d+)\}\{([^}]*)\}/g)) {
    if (m.index > i) palabras.push({ t: limpiar(cuerpo.slice(i, m.index)), w: 0 });
    palabras.push({ t: limpiar(m[2]), w: Number(m[1]) });
    i = m.index + m[0].length;
  }
  if (i < cuerpo.length) palabras.push({ t: limpiar(cuerpo.slice(i)), w: 0 });
  return { codigo, descripcion, palabras };
}

const html = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');

async function llamar(informe) {
  const base = process.env.AI_URL ?? 'http://host.docker.internal:8000';
  const t0 = performance.now();
  const r = await fetch(`${base}/predict`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ text: informe }),
  });
  const ms = Math.round(performance.now() - t0);
  if (!r.ok) throw new Error(`motor.mjs: /predict respondió ${r.status}`);
  const j = await r.json();
  const tarjeta = (j.cards ?? []).find((c) => c.type === 'codes');
  const codigos = (tarjeta?.content ?? j.codes ?? []).slice(0, 3).map((c) => ({
    code: c.code,
    description: c.description,
    confidence: Number(c.confidence).toFixed(2),
    triggers: c.triggers ?? [],
  }));
  if (!codigos.length) throw new Error('motor.mjs: /predict no devolvió códigos');
  const corto = informe.replace(/\s+/g, ' ').slice(0, 72).replace(/\s+\S*$/, '');
  return { estado: `${r.status} OK`, ms, texto: html(corto) + '…', codigos };
}

let datos;

export default async (v, lib, args = {}) => {
  const { page } = v;
  const preparar = () => page.evaluate((d) => window.preparar(d), datos);
  switch (args.accion) {
    case 'abrir': {
      const cfg = json('ai_engine/model/config.json');
      datos = {
        ...memoria(),
        modelo: cfg.model_name,
        maxTokens: cfg.max_length,
        umbral: cfg.threshold,
        beta: cfg.fusion_beta,
        motores: motores(),
        explicacion: explicacion(),
      };
      await page.goto('file://' + PAGINA, { waitUntil: 'load' });
      await preparar();
      return;
    }
    case 'escena':
      if (args.n === 6) {
        datos.api = await llamar(args.informe);
        await preparar();
      }
      await page.evaluate((n) => window.escena(n), args.n);
      return;
    default:
      throw new Error(`motor.mjs: acción desconocida "${args.accion}"`);
  }
};
