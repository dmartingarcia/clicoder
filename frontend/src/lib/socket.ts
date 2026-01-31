import { Socket } from 'phoenix';

let socket: Socket | null = null;

export function getSocket(userId: string): Socket {
  if (!socket) {
    socket = new Socket('ws://localhost:4000/socket', {
      params: { user_id: userId },
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
