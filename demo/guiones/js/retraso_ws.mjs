export default async (v, lib, args) => {
  const ms = args.ms ?? 300;
  const resumen = args.resumen;
  const visto = new Set();
  const reescribir = (msg) => {
    if (!resumen || typeof msg !== 'string') return msg;
    let m;
    try {
      m = JSON.parse(msg);
    } catch {
      return msg;
    }
    if (!Array.isArray(m)) return msg;
    const [, , , evento, payload] = m;
    if (evento === 'summary_token') {
      if (visto.has(payload.message_id)) return null;
      visto.add(payload.message_id);
      payload.token = resumen;
    } else if (evento === 'analysis_card_received' && payload.card_type === 'summary') {
      payload.content = resumen;
    } else return msg;
    return JSON.stringify(m);
  };
  await v.page.routeWebSocket(/\/socket/, (ws) => {
    const server = ws.connectToServer();
    ws.onMessage((msg) => {
      if (typeof msg === 'string' && msg.includes('analyze_report')) setTimeout(() => server.send(msg), ms);
      else server.send(msg);
    });
    server.onMessage((msg) => {
      const salida = reescribir(msg);
      if (salida !== null) ws.send(salida);
    });
  });
};
