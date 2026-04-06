import { useEffect, useState, useCallback } from 'react';
import { TooltipProvider } from './components/ui/tooltip';
import { socketService } from './lib/socket';
import { api, Seat, Stats, Alert, Zone, HistoryPoint } from './lib/api';
import { Header } from './components/Header';
import { StatsBar } from './components/StatsBar';
import { SeatMap } from './components/SeatMap';
import { OccupancyChart } from './components/OccupancyChart';
import { AlertFeed } from './components/AlertFeed';
import { SeatDialog } from './components/SeatDialog';
import { Toaster } from './components/ui/toaster';
import { useToast } from './hooks/use-toast';

const ZONE_NAMES = ['Z1', 'Z2', 'Z3', 'Z4', 'Z5', 'Z6', 'Z7'];

function App() {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [seats, setSeats] = useState<Record<string, Seat>>({});
  const [zones, setZones] = useState<Record<string, Zone>>({});
  const [stats, setStats] = useState<Stats>({
    occupied: 0, empty: 0, ghost: 0, suspected: 0, total_scans: 0, utilization: 0
  });
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [selectedSeat, setSelectedSeat] = useState<Seat | null>(null);
  const [currentRoom, setCurrentRoom] = useState('room_1');
  const { toast } = useToast();

  // Poll for REST API updates as fallback when WebSocket isn't available
  useEffect(() => {
    const pollState = async () => {
      try {
        const data = await api.getState();
        if (data.seats) setSeats(data.seats);
        if (data.stats) setStats(data.stats);
        if (data.zones) setZones(data.zones);
        if (data.alerts) setAlerts(data.alerts);
        setConnected(true);
        setLoading(false);
      } catch (err) {
        setConnected(false);
      }
    };

    // Initial fetch
    pollState();

    // Poll every 3 seconds
    const interval = setInterval(pollState, 3000);
    return () => clearInterval(interval);
  }, []);

  // Try Socket.IO but don't rely on it
  useEffect(() => {
    socketService.connect();

    socketService.on('connection_change', (conn: boolean) => {
      if (conn) setConnected(true);
    });

    socketService.on('seat_state', (data: { seats: Record<string, Seat> }) => {
      setSeats(data.seats);
    });

    socketService.on('stats', (newStats: Stats) => {
      setStats(newStats);
    });

    socketService.on('alert', (alert: Alert) => {
      setAlerts(prev => [alert, ...prev].slice(0, 50));
      toast({
        title: alert.type.replace('_', ' ').toUpperCase(),
        description: `${alert.seat_id}: ${alert.message}`,
        variant: alert.type.includes('critical') ? 'destructive' : 'default',
      });
    });

    return () => {
      socketService.disconnect();
    };
  }, [toast]);

  const handleSelectRoom = useCallback(async (roomId: string) => {
    setCurrentRoom(roomId);
    await api.selectRoom(roomId);
    const data = await api.getState();
    if (data.seats) setSeats(data.seats);
    if (data.stats) setStats(data.stats);
  }, []);

  const handleAcknowledgeAlert = useCallback(async (alertId: string) => {
    await api.acknowledgeAlert(alertId);
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
  }, []);

  const handleResolveAlert = useCallback(async (alertId: string) => {
    await api.resolveAlert(alertId);
    setAlerts(prev => prev.filter(a => a.id !== alertId));
  }, []);

  const handleSnoozeAlert = useCallback(async (alertId: string) => {
    await api.snoozeAlert(alertId);
    setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, acknowledged: true } : a));
  }, []);

  // Group seats by zone
  const seatsByZone: Record<string, Seat[]> = {};
  ZONE_NAMES.forEach(zone => {
    seatsByZone[zone] = [];
  });
  Object.values(seats).forEach(seat => {
    const zone = seat.zone || 'Z1';
    if (seatsByZone[zone]) {
      seatsByZone[zone].push(seat);
    }
  });

  // Calculate zone occupancy
  const zoneStats: Record<string, { occupied: number; total: number; status: string }> = {};
  ZONE_NAMES.forEach(zone => {
    const zoneSeats = seatsByZone[zone] || [];
    const occupied = zoneSeats.filter(s => s.state === 'occupied' || s.state === 'suspected' || s.state === 'confirmed').length;
    const total = zoneSeats.length || 4;
    let status = 'empty';
    if (occupied > 0) status = 'occupied';
    zoneStats[zone] = { occupied, total, status };
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#09090b' }}>
        <div className="flex flex-col items-center gap-6">
          <div className="w-10 h-10 border-2 border-white/10 border-t-white/50 rounded-full animate-spin" />
          <div className="text-center">
            <p className="text-base font-medium text-white/80">Loading LibertyTwin</p>
            <p className="text-sm text-white/40 mt-1">Connecting to sensors...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider>
    <div className="min-h-screen" style={{ background: '#09090b' }}>
      {/* Header */}
      <Header
        connected={connected}
        currentRoom={currentRoom}
        onSelectRoom={handleSelectRoom}
      />

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {/* Stats Overview - 4 equal columns */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatsBar stats={stats} />
        </div>

        {/* Main Grid - Bento Style */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Left Column - Floor Plan & Seats */}
          <div className="xl:col-span-8 space-y-6">
            {/* Floor Plan */}
            <div className="floor-plan">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold">Floor Plan</h2>
                  <p className="text-sm text-white/40 mt-1">Real-time zone occupancy</p>
                </div>
                <div className="flex items-center gap-2 text-xs text-white/50">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                  Live
                </div>
              </div>
              <div className="grid grid-cols-4 gap-4">
                {ZONE_NAMES.map((zone, idx) => {
                  const zStat = zoneStats[zone] || { occupied: 0, total: 4, status: 'empty' };
                  return (
                    <div
                      key={zone}
                      className={`zone-card ${zStat.status}`}
                      style={{ animationDelay: `${idx * 50}ms` }}
                    >
                      <div className="text-sm font-medium text-white/50">{zone}</div>
                      <div className="text-4xl font-bold text-white mt-1">
                        {zStat.occupied}
                        <span className="text-lg text-white/30">/{zStat.total}</span>
                      </div>
                      <div className="text-xs text-white/40 mt-1">
                        {zStat.occupied > 0 ? 'Occupied' : 'Available'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Seat Grid */}
            <SeatMap seats={seats} onSeatClick={setSelectedSeat} />
          </div>

          {/* Right Column - Chart & Alerts */}
          <div className="xl:col-span-4 space-y-6">
            {/* Occupancy Chart */}
            <OccupancyChart history={history} />

            {/* Alert Feed */}
            <AlertFeed
              alerts={alerts}
              onAcknowledge={handleAcknowledgeAlert}
              onResolve={handleResolveAlert}
              onSnooze={handleSnoozeAlert}
            />
          </div>
        </div>
      </main>

      <SeatDialog
        seat={selectedSeat}
        onClose={() => setSelectedSeat(null)}
      />

      <Toaster />
    </div>
    </TooltipProvider>
  );
}

export default App;
