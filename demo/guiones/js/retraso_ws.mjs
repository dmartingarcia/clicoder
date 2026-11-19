export default async (v, lib, args) => {
  const ms = args.ms ?? 300;
  await v.page.routeWebSocket(/\/socket/, (ws) => {
    const server = ws.connectToServer();
    ws.onMessage((msg) => {
      if (typeof msg === 'string' && msg.includes('analyze_report')) setTimeout(() => server.send(msg), ms);
      else server.send(msg);
    });
    server.onMessage((msg) => ws.send(msg));
  });
};
