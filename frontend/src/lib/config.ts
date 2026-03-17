export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api',
  wsUrl: process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:4000/socket',
};
