import { useEffect, useState } from 'react';
import { Radio, MapPin } from 'lucide-react';
import { Badge } from './ui/badge';
import { api } from '@/lib/api';

interface HeaderProps {
  connected: boolean;
  currentRoom: string;
  onSelectRoom: (roomId: string) => void;
}

export function Header({ connected, currentRoom, onSelectRoom }: HeaderProps) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const rooms = [
    { id: 'room_1', name: 'Main Library' },
    { id: 'room_2', name: 'Study Hall' },
    { id: 'room_3', name: 'Reference Section' },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-white/5" style={{ background: '#09090b' }}>
      <div className="container mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: '#27272a' }}>
                <Radio className="w-5 h-5 text-white/80" />
              </div>
              <div>
                <h1 className="text-lg font-semibold tracking-tight">
                  LibertyTwin
                </h1>
                <p className="text-xs text-white/40">IoT Dashboard</p>
              </div>
            </div>

            {/* Live indicator */}
            <Badge
              variant="outline"
              className="text-xs font-medium border-white/10"
            >
              <span className={`w-1.5 h-1.5 rounded-full mr-2 ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
              {connected ? 'Live' : 'Offline'}
            </Badge>
          </div>

          {/* Room Selector - Center */}
          <div className="flex items-center gap-3">
            <div className="room-selector">
              <select
                value={currentRoom}
                onChange={(e) => onSelectRoom(e.target.value)}
                className="appearance-none bg-zinc-900 border border-white/10 rounded-lg px-4 py-2 pr-9 text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 cursor-pointer transition-colors"
              >
                {rooms.map(room => (
                  <option key={room.id} value={room.id} className="bg-zinc-900">
                    {room.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Clock */}
          <div className="text-right">
            <div
              className="text-xl font-semibold tracking-tight text-white"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              {time.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
            <div className="text-xs text-white/40">
              {time.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
