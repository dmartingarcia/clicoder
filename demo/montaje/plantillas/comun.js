(function () {
  const TAU = Math.PI * 2;
  const PERIODO = 8;

  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const E = {
    outExpo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),
    outCubic: (x) => 1 - Math.pow(1 - x, 3),
    inCubic: (x) => x * x * x,
    inOutCubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    outBack: (x, s = 1.70158) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
  };

  function rng(semilla) {
    let a = semilla >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function rgb(c) {
    const h = String(c).replace('#', '');
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  }
  const mezcla = (c1, c2, k) => {
    const a = rgb(c1), b = rgb(c2);
    return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, '0')).join('');
  };
  const rgba = (c, a) => {
    const [r, g, b] = rgb(c);
    return `rgba(${r},${g},${b},${a})`;
  };

  let lo = null;
  function fondo(ctx, W, H, T, P) {
    if (!lo) {
      lo = document.createElement('canvas');
      lo.width = 480;
      lo.height = 270;
    }
    const c = lo.getContext('2d');
    const w = lo.width, h = lo.height;
    c.globalCompositeOperation = 'source-over';
    c.fillStyle = P.BASE;
    c.fillRect(0, 0, w, h);
    const fase = (TAU * T) / PERIODO;
    const claro = mezcla(P.A, '#ffffff', 0.35);
    const hondo = mezcla(P.B, '#000000', 0.45);
    const manchas = [
      [P.A, 0.22, 0.3, 0.12, 0.1, 1, 0.0, 0.62, 0.72],
      [P.B, 0.78, 0.25, 0.1, 0.14, 1, 2.1, 0.66, 0.78],
      [claro, 0.55, 0.82, 0.14, 0.08, 2, 4.0, 0.5, 0.5],
      [P.ACC, 0.9, 0.88, 0.05, 0.06, 1, 1.0, 0.3, 0.32],
      [hondo, 0.12, 0.88, 0.1, 0.07, 2, 5.2, 0.55, 0.85],
    ];
    c.globalCompositeOperation = 'screen';
    for (const [col, bx, by, ax, ay, k, ph, r, al] of manchas) {
      const cx = (bx + ax * Math.sin(fase * k + ph)) * w;
      const cy = (by + ay * Math.cos(fase * k + ph * 1.3)) * h;
      const g = c.createRadialGradient(cx, cy, 0, cx, cy, r * w);
      g.addColorStop(0, rgba(col, al));
      g.addColorStop(0.55, rgba(col, al * 0.35));
      g.addColorStop(1, rgba(col, 0));
      c.fillStyle = g;
      c.fillRect(0, 0, w, h);
    }
    c.globalCompositeOperation = 'source-over';
    const v = c.createRadialGradient(w / 2, h / 2, h * 0.35, w / 2, h / 2, w * 0.72);
    v.addColorStop(0, 'rgba(0,0,0,0)');
    v.addColorStop(1, 'rgba(0,0,0,0.62)');
    c.fillStyle = v;
    c.fillRect(0, 0, w, h);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(lo, 0, 0, W, H);
  }

  const PART = (() => {
    const r = rng(20260115);
    return Array.from({ length: 70 }, () => ({
      x: r(), y: r(), v: 1 + Math.floor(r() * 2), fx: r() * TAU,
      tam: 1.1 + r() * 2.8, kt: 1 + Math.floor(r() * 3), ft: r() * TAU, a: 0.15 + r() * 0.4,
    }));
  })();
  function particulas(ctx, W, H, T, P, intensidad = 1) {
    const esc = H / 1080;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (const p of PART) {
      const y = (((p.y - (p.v * T) / PERIODO) % 1) + 1) % 1;
      const x = p.x + 0.012 * Math.sin((TAU * T * p.v) / PERIODO + p.fx);
      const tw = 0.5 + 0.5 * Math.sin((TAU * T * p.kt) / PERIODO + p.ft);
      const borde = Math.min(1, y * 6, (1 - y) * 6);
      const a = p.a * (0.35 + 0.65 * tw) * borde * intensidad;
      const px = x * W, py = y * H, r = p.tam * esc * 2.6;
      const g = ctx.createRadialGradient(px, py, 0, px, py, r);
      g.addColorStop(0, `rgba(255,255,255,${a})`);
      g.addColorStop(0.4, rgba(P.ACC, a * 0.35));
      g.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = g;
      ctx.fillRect(px - r, py - r, r * 2, r * 2);
    }
    ctx.restore();
  }


  const LOGO_SVG = (px) => `
    <svg width="${px}" height="${px}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7"
         stroke-linecap="round" stroke-linejoin="round">
      <path class="tr" pathLength="1" d="M11 2v2"/>
      <path class="tr" pathLength="1" d="M5 2v2"/>
      <path class="tr" pathLength="1" d="M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1"/>
      <path class="tr" pathLength="1" d="M8 15a6 6 0 0 0 12 0v-3"/>
      <circle class="tr" pathLength="1" cx="20" cy="10" r="2"/>
    </svg>`;
  function dibujarLogo(raiz, prog) {
    const trazos = raiz.querySelectorAll('.tr');
    const n = trazos.length;
    trazos.forEach((el, i) => {
      const p = E.inOutCubic(seg(prog, (i / n) * 0.55, (i / n) * 0.55 + 0.45));
      el.style.strokeDasharray = '1';
      el.style.strokeDashoffset = String(1 - p);
    });
  }

  function palabras(contenedor, texto) {
    contenedor.innerHTML = '';
    const out = [];
    for (const w of String(texto).split(/\s+/).filter(Boolean)) {
      const caja = document.createElement('span');
      caja.className = 'pal';
      const dentro = document.createElement('span');
      dentro.textContent = w;
      caja.appendChild(dentro);
      contenedor.appendChild(caja);
      out.push(dentro);
    }
    return out;
  }
  function animarPalabras(lista, t, t0, { escalon = 0.085, dur = 0.8, desp = 115 } = {}) {
    lista.forEach((el, i) => {
      const p = E.outExpo(seg(t, t0 + i * escalon, t0 + i * escalon + dur));
      el.style.transform = `translateY(${(1 - p) * desp}%)`;
      el.style.filter = `blur(${(1 - p) * 14}px)`;
      el.style.opacity = String(clamp(p * 1.6));
    });
  }

  window.MC = { TAU, PERIODO, clamp, seg, E, rng, rgb, mezcla, rgba, fondo, particulas, LOGO_SVG, dibujarLogo, palabras, animarPalabras };
})();
