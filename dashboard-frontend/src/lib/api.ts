const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export interface Seat {
  seat_id: string;
  zone: string;
  state: 'empty' | 'occupied' | 'suspected' | 'confirmed';
  occupancy_score: number;
  object_type: string;
  confidence: number;
  is_present: boolean;
  has_motion: boolean;
  radar_presence: number;
  radar_motion: number;
  timestamp: number;
}

export interface Stats {
  occupied: number;
  empty: number;
  ghost: number;
  suspected: number;
  total_scans: number;
  utilization: number;
}

export interface Alert {
  id: string;
  type: string;
  message: string;
  seat_id: string;
  zone: string;
  countdown: number;
  timestamp: string;
  acknowledged: boolean;
  snoozed_until?: number;
}

export interface Zone {
  name: string;
  occupied: number;
  total: number;
  seats: Record<string, Seat>;
}

export interface HistoryPoint {
  ts: string;
  occupied: number;
  empty: number;
  ghost: number;
  suspected: number;
  total: number;
}

export interface Room {
  room_id: string;
  name: string;
  zones: number;
  seat_count: number;
  occupied: number;
  utilization: number;
  last_update: number;
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export const api = {
  getState: () => fetchJson<{
    seats: Record<string, Seat>;
    zones: Record<string, Zone>;
    stats: Stats;
    alerts: Alert[];
    current_room: string;
  }>('/api/state'),

  getRooms: () => fetchJson<{
    rooms: Record<string, { name: string; zones: number }>;
    current_room: string;
  }>('/api/rooms'),

  selectRoom: (roomId: string) =>
    fetchJson<{ status: string; current_room: string }>(`/api/rooms/${roomId}/select`, {
      method: 'POST',
    }),

  getAlerts: (includeAcked = true) =>
    fetchJson<{ alerts: Alert[]; total: number }>(
      `/api/alerts?include_acked=${includeAcked}`
    ),

  acknowledgeAlert: (alertId: string, userId = 'dashboard') =>
    fetchJson<{ status: string }>(`/api/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),

  snoozeAlert: (alertId: string, duration = 300) =>
    fetchJson<{ status: string }>(`/api/alerts/${alertId}/snooze`, {
      method: 'POST',
      body: JSON.stringify({ duration }),
    }),

  resolveAlert: (alertId: string) =>
    fetchJson<{ status: string }>(`/api/alerts/${alertId}/resolve`, {
      method: 'POST',
    }),

  getHistory: (minutes = 60) =>
    fetchJson<HistoryPoint[]>(`/api/history?minutes=${minutes}`),

  setTheme: (theme: 'dark' | 'light') =>
    fetchJson<{ status: string }>('/api/settings/theme', {
      method: 'POST',
      body: JSON.stringify({ theme }),
    }),

  setSound: (enabled: boolean) =>
    fetchJson<{ status: string }>('/api/settings/sound', {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),
};
