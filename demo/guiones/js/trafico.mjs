const API = process.env.API_URL ?? 'http://host.docker.internal:4000/api';

const rutas = [
  '/health',
  '/translations/es',
  '/cie10/search?q=hipertension',
  '/cie10/codes/I10',
  '/translations/en',
  '/cie10/search?q=diabetes',
  '/cie10/codes/E11.9',
  '/cie10/codes/J45.9/children',
];

export default async (v, lib, args = {}) => {
  if (args.accion === 'parar') {
    v.trafico?.parar();
    await v.trafico?.bucle;
    return;
  }
  let activo = true;
  const bucle = (async () => {
    for (let i = 0; activo; i++) {
      await fetch(API + rutas[i % rutas.length]).catch(() => {});
      await new Promise((r) => setTimeout(r, args.cada ?? 160));
    }
  })();
  v.trafico = { parar: () => (activo = false), bucle };
};
