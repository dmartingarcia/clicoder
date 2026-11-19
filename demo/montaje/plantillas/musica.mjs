import { writeFileSync } from 'node:fs';

const SR = 44100;
const TAU = Math.PI * 2;
const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
const suave = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };

const PROG = {
  mayor: [[48, [0, 4, 7, 11]], [45, [0, 3, 7, 10]], [41, [0, 4, 7, 11]], [43, [0, 4, 7, 9]]],
  menor: [[45, [0, 3, 7, 10]], [41, [0, 4, 7, 11]], [48, [0, 4, 7, 14]], [43, [0, 4, 7, 10]]],
};

export function generarMusica({ dur, bpm = 96, escala = 'mayor', tonos = null, ruta }) {
  const beat = 60 / bpm;
  const bar = 4 * beat;
  const Lb = Math.round(4 * bar * SR);
  const prog = PROG[escala] || PROG.mayor;
  const N = Math.ceil((dur + 1) * SR);

  const acordes = tonos && tonos.length
    ? [0, 1, 2, 3].map(() => ({ freqs: tonos, raiz: Math.min(...tonos) / 2 }))
    : prog.map(([r, iv]) => ({ freqs: iv.map((i) => mtof(r + i)), raiz: mtof(r - 12), r }));

  const nuevo = () => new Float32Array(Lb);
  const pL = nuevo(), pR = nuevo(), bajo = nuevo(), arp = nuevo(), kick = nuevo(), hat = nuevo();
  const add = (buf, i, v) => { buf[((i % Lb) + Lb) % Lb] += v; };

  for (let c = 0; c < 4; c++) {
    const ini = Math.round(c * bar * SR);
    const largo = Math.round((bar + 1.3) * SR);
    for (const [buf, cents] of [[pL, 6], [pR, -6]]) {
      const k = Math.pow(2, cents / 1200);
      acordes[c].freqs.forEach((f0, idx) => {
        const nota = [f0, idx < 2 ? f0 * 2 : 0].filter(Boolean);
        for (const f of nota) {
          const amp = f === f0 ? 0.052 : 0.026;
          for (let n = 0; n < largo; n++) {
            const t = n / SR;
            const att = suave(t / 0.9);
            const rel = suave((bar + 1.3 - t) / 1.3);
            const env = att * rel;
            let s = 0;
            for (let h = 1; h <= 5; h++) s += Math.sin(TAU * f * k * h * t + idx) / h;
            add(buf, ini + n, s * env * amp);
          }
        }
      });
    }
  }
  for (const buf of [pL, pR]) {
    let y = 0;
    for (let i = 0; i < Lb; i++) {
      const fc = 1100 + 500 * Math.sin((TAU * i) / Lb);
      const a = 1 - Math.exp((-TAU * fc) / SR);
      y += a * (buf[i] - y);
      buf[i] = y;
    }
    for (let i = 0; i < Math.round(SR * 0.5); i++) {
      const fc = 1100;
      const a = 1 - Math.exp((-TAU * fc) / SR);
      y += a * (buf[i] - y);
      buf[i] = y;
    }
  }

  for (let c = 0; c < 4; c++) {
    const f = acordes[c].raiz;
    const ini = Math.round(c * bar * SR);
    const largo = Math.round(bar * 0.98 * SR);
    for (let n = 0; n < largo; n++) {
      const t = n / SR;
      const env = suave(t / 0.04) * Math.exp(-t * 0.55) * suave((bar * 0.98 - t) / 0.25);
      add(bajo, ini + n, (Math.sin(TAU * f * t) + 0.22 * Math.sin(TAU * f * 2 * t)) * env * 0.2);
    }
  }

  const patron = [0, 2, 1, 3, 2, 1, 3, 2];
  for (let c = 0; c < 4; c++) {
    const tonos4 = acordes[c].freqs.map((f) => f * 4);
    for (let s = 0; s < 8; s++) {
      if (s === 5) continue;
      const f = tonos4[patron[s] % tonos4.length];
      const ini = Math.round((c * bar + s * beat * 0.5) * SR);
      const acento = s % 2 === 0 ? 1.25 : 0.85;
      const largo = Math.round(0.9 * SR);
      for (let n = 0; n < largo; n++) {
        const t = n / SR;
        const env = suave(t / 0.004) * Math.exp(-t / 0.2);
        add(arp, ini + n, (Math.sin(TAU * f * t) + 0.32 * Math.sin(TAU * f * 2 * t) + 0.1 * Math.sin(TAU * f * 3 * t)) * env * 0.1 * acento);
      }
    }
  }

  let ruido = 12345;
  const azar = () => ((ruido = (Math.imul(ruido, 1664525) + 1013904223) >>> 0) / 4294967296) * 2 - 1;
  for (let c = 0; c < 4; c++) {
    for (const tiempo of [0, 2]) {
      const ini = Math.round((c * bar + tiempo * beat) * SR);
      const largo = Math.round(0.45 * SR);
      let fase = 0;
      for (let n = 0; n < largo; n++) {
        const t = n / SR;
        const f = 46 + 70 * Math.exp(-t / 0.035);
        fase += (TAU * f) / SR;
        add(kick, ini + n, Math.sin(fase) * Math.exp(-t / 0.13) * 0.3 * suave(t / 0.002));
      }
    }
    for (const s of [1, 3, 5, 7]) {
      const ini = Math.round((c * bar + s * beat * 0.5) * SR);
      const largo = Math.round(0.05 * SR);
      let prev = 0;
      for (let n = 0; n < largo; n++) {
        const r = azar();
        add(hat, ini + n, (r - prev) * Math.exp(-(n / SR) / 0.012) * 0.03);
        prev = r;
      }
    }
  }

  const L = new Float32Array(N), R = new Float32Array(N), envio = new Float32Array(N);
  const g = (t, desde, rampa) => suave((t - desde) / rampa);
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    const j = i % Lb;
    const gp = g(t, 0, 2.5), gb = g(t, bar * 1, 2), ga = g(t, bar * 2, 2), gk = g(t, bar * 3, 1.5);
    const pad = [pL[j] * gp, pR[j] * gp];
    const b = bajo[j] * gb;
    const a = arp[j] * ga;
    const k = kick[j] * gk + hat[j] * gk;
    L[i] = pad[0] + b + a * 0.7 + k;
    R[i] = pad[1] + b + a * 0.7 + k;
    envio[i] = (pad[0] + pad[1]) * 0.5 * 0.55 + a * 0.6;
  }

  {
    const d = Math.round(0.75 * beat * SR);
    const bL = new Float32Array(d), bR = new Float32Array(d);
    let lpL = 0, lpR = 0;
    for (let i = 0; i < N; i++) {
      const x = arp[i % Lb] * g(i / SR, bar * 2, 2);
      const eL = bL[i % d], eR = bR[i % d];
      lpL += 0.45 * (eR - lpL);
      lpR += 0.45 * (eL - lpR);
      bL[i % d] = x * 0.9 + lpL * 0.42;
      bR[i % d] = lpR * 0.42;
      L[i] += eL * 0.8;
      R[i] += eR * 0.8;
      envio[i] += (eL + eR) * 0.25;
    }
  }

  function reverb(entrada, desfase) {
    const combs = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617].map((d) => d + desfase);
    const aps = [556, 441, 341, 225].map((d) => d + desfase);
    const cb = combs.map((d) => ({ b: new Float32Array(d), i: 0, f: 0 }));
    const ab = aps.map((d) => ({ b: new Float32Array(d), i: 0 }));
    const out = new Float32Array(entrada.length);
    for (let n = 0; n < entrada.length; n++) {
      const x = entrada[n] * 0.015;
      let y = 0;
      for (const c of cb) {
        const v = c.b[c.i];
        c.f = v * 0.8 + c.f * 0.2;
        c.b[c.i] = x + c.f * 0.86;
        if (++c.i >= c.b.length) c.i = 0;
        y += v;
      }
      for (const a of ab) {
        const v = a.b[a.i];
        const z = y + v * 0.5;
        a.b[a.i] = z;
        y = v - z * 0.5;
        if (++a.i >= a.b.length) a.i = 0;
      }
      out[n] = y;
    }
    return out;
  }
  const rL = reverb(envio, 0), rR = reverb(envio, 23);
  let pico = 1e-9;
  for (let i = 0; i < N; i++) {
    L[i] += rL[i] * 5;
    R[i] += rR[i] * 5;
    pico = Math.max(pico, Math.abs(L[i]), Math.abs(R[i]));
  }

  const datos = new Int16Array(N * 2);
  const k = 0.9 / pico;
  for (let i = 0; i < N; i++) {
    datos[2 * i] = Math.max(-32767, Math.min(32767, Math.round(L[i] * k * 32767)));
    datos[2 * i + 1] = Math.max(-32767, Math.min(32767, Math.round(R[i] * k * 32767)));
  }
  const cab = Buffer.alloc(44);
  cab.write('RIFF', 0); cab.writeUInt32LE(36 + datos.byteLength, 4); cab.write('WAVEfmt ', 8);
  cab.writeUInt32LE(16, 16); cab.writeUInt16LE(1, 20); cab.writeUInt16LE(2, 22);
  cab.writeUInt32LE(SR, 24); cab.writeUInt32LE(SR * 4, 28); cab.writeUInt16LE(4, 32); cab.writeUInt16LE(16, 34);
  cab.write('data', 36); cab.writeUInt32LE(datos.byteLength, 40);
  writeFileSync(ruta, Buffer.concat([cab, Buffer.from(datos.buffer)]));
}
