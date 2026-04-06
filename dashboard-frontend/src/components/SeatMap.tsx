import { Seat } from '@/lib/api';
import { Card } from './ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from './ui/tooltip';

interface SeatMapProps {
  seats: Record<string, Seat>;
  onSeatClick: (seat: Seat) => void;
}

export function SeatMap({ seats, onSeatClick }: SeatMapProps) {
  const seatIds = Array.from({ length: 28 }, (_, i) => `S${i + 1}`);

  const getStateClass = (state: string = 'empty') => {
    switch (state) {
      case 'occupied': return 'occupied';
      case 'suspected': return 'suspected';
      case 'confirmed': return 'confirmed';
      default: return 'empty';
    }
  };

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">Seat Status</h2>
        <div className="flex gap-4 text-xs text-white/50">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-green-500/30" />
            Empty
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-red-500/30" />
            Occupied
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-yellow-500/30" />
            Suspected
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded bg-purple-500/30" />
            Ghost
          </span>
        </div>
      </div>

      <div className="seat-grid">
        {seatIds.map((seatId, index) => {
          const seat = seats[seatId];
          const state = seat?.state || 'empty';
          const stateClass = getStateClass(state);

          return (
            <Tooltip key={seatId}>
              <TooltipTrigger asChild>
                <button
                  onClick={() => seat && onSeatClick(seat)}
                  className={`
                    seat-dot ${stateClass} animate-fade-in
                    ${!seat ? 'opacity-30' : ''}
                  `}
                  style={{ animationDelay: `${index * 15}ms` }}
                  disabled={!seat}
                >
                  <span className="text-[9px] font-semibold">
                    {seatId.replace('S', '')}
                  </span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="bg-zinc-900 border-zinc-800">
                <div className="text-sm">
                  <p className="font-semibold">{seatId}</p>
                  {seat ? (
                    <div className="space-y-1 mt-1">
                      <p className="text-xs text-white/60">
                        State: <span className={
                          state === 'occupied' ? 'text-red-400' :
                          state === 'suspected' ? 'text-yellow-400' :
                          state === 'confirmed' ? 'text-purple-400' :
                          'text-green-400'
                        }>{state}</span>
                      </p>
                      <p className="text-xs text-white/60">
                        Score: {(seat.occupancy_score * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-white/60">
                        {seat.object_type || 'empty'}
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-white/60">No data</p>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>

      {/* Zone dividers */}
      <div className="mt-4 pt-4 border-t border-white/5">
        <div className="flex justify-between text-xs text-white/40">
          <span>Z1-Z4 (Back)</span>
          <span>Z5-Z7 (Front)</span>
        </div>
      </div>
    </Card>
  );
}
