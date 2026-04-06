import { io, Socket } from 'socket.io-client';

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

class SocketService {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<Function>> = new Map();

  connect() {
    if (this.socket?.connected) return;

    this.socket = io(SOCKET_URL, {
      transports: ['polling', 'websocket'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
    });

    this.socket.on('connect', () => {
      console.log('[Socket] Connected');
      this.emit('connection_change', true);
    });

    this.socket.on('disconnect', () => {
      console.log('[Socket] Disconnected');
      this.emit('connection_change', false);
    });

    this.socket.on('seat_state', (data) => this.emit('seat_state', data));
    this.socket.on('stats', (data) => this.emit('stats', data));
    this.socket.on('telemetry', (data) => this.emit('telemetry', data));
    this.socket.on('ghost_alert', (data) => this.emit('ghost_alert', data));
    this.socket.on('alert_acknowledged', (data) => this.emit('alert_acknowledged', data));
    this.socket.on('alert_resolved', (data) => this.emit('alert_resolved', data));
    this.socket.on('history_data', (data) => this.emit('history_data', data));
    this.socket.on('room_changed', (data) => this.emit('room_changed', data));
  }

  disconnect() {
    this.socket?.disconnect();
    this.socket = null;
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback);
  }

  off(event: string, callback: Function) {
    this.listeners.get(event)?.delete(callback);
  }

  private emit(event: string, data: any) {
    this.listeners.get(event)?.forEach(cb => cb(data));
  }

  isConnected() {
    return this.socket?.connected ?? false;
  }
}

export const socketService = new SocketService();
