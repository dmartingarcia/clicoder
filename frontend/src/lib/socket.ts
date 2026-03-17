import { Socket } from 'phoenix';
import { config } from '@/lib/config';

let socket: Socket | null = null;

export function getSocket(token: string): Socket {
  if (!socket) {
    socket = new Socket(config.wsUrl, {
      params: { token },
    });
    socket.connect();
  }
  return socket;
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
