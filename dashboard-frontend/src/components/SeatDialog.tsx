import { Seat } from '@/lib/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { Separator } from './ui/separator';
import { Armchair, Activity, Radar, Clock, Check } from 'lucide-react';

interface SeatDialogProps {
  seat: Seat | null;
  onClose: () => void;
}

export function SeatDialog({ seat, onClose }: SeatDialogProps) {
  if (!seat) return null;

  const getStateColor = (state: string) => {
    switch (state) {
      case 'occupied': return 'bg-red-500';
      case 'suspected': return 'bg-yellow-500';
      case 'confirmed': return 'bg-purple-500';
      default: return 'bg-green-500';
    }
  };

  return (
    <Dialog open={!!seat} onOpenChange={() => onClose()}>
      <DialogContent className="sm:max-w-[400px] glass">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <div className={`
              w-10 h-10 rounded-xl flex items-center justify-center
              ${seat.state === 'occupied' ? 'bg-red-500/20' :
                seat.state === 'suspected' ? 'bg-yellow-500/20' :
                seat.state === 'confirmed' ? 'bg-purple-500/20' :
                'bg-green-500/20'}
            `}>
              <Armchair className={`
                w-5 h-5
                ${seat.state === 'occupied' ? 'text-red-400' :
                  seat.state === 'suspected' ? 'text-yellow-400' :
                  seat.state === 'confirmed' ? 'text-purple-400' :
                  'text-green-400'}
              `} />
            </div>
            <div>
              <span className="text-xl">{seat.seat_id}</span>
              <Badge
                variant="outline"
                className={`
                  ml-2 text-xs
                  ${seat.state === 'occupied' ? 'border-red-500/50 text-red-400' :
                    seat.state === 'suspected' ? 'border-yellow-500/50 text-yellow-400' :
                    seat.state === 'confirmed' ? 'border-purple-500/50 text-purple-400' :
                    'border-green-500/50 text-green-400'}
                `}
              >
                {seat.state}
              </Badge>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {/* Occupancy Score */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Occupancy Score</span>
              <span className="font-medium">
                {(seat.occupancy_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="relative">
              <Progress value={seat.occupancy_score * 100} className="h-2" />
              <div
                className={`absolute top-0 left-0 h-full rounded-full transition-all ${getStateColor(seat.state)} opacity-30`}
                style={{ width: `${seat.occupancy_score * 100}%` }}
              />
            </div>
          </div>

          <Separator />

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Activity className="w-3 h-3" /> Object Type
              </p>
              <p className="text-sm font-medium capitalize">
                {seat.object_type || 'empty'}
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Radar className="w-3 h-3" /> Confidence
              </p>
              <p className="text-sm font-medium">
                {(seat.confidence * 100).toFixed(0)}%
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Zone</p>
              <p className="text-sm font-medium">{seat.zone}</p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Motion</p>
              <p className="text-sm font-medium flex items-center gap-1">
                {seat.has_motion ? (
                  <>
                    <Check className="w-3 h-3 text-green-400" />
                    <span className="text-green-400">Active</span>
                  </>
                ) : (
                  <span className="text-muted-foreground">None</span>
                )}
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Radar className="w-3 h-3" /> Radar Presence
              </p>
              <p className="text-sm font-medium">
                {(seat.radar_presence * 100).toFixed(0)}%
              </p>
            </div>

            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" /> Last Update
              </p>
              <p className="text-sm font-medium">
                {seat.timestamp
                  ? new Date(seat.timestamp * 1000).toLocaleTimeString('en-US', {
                      hour12: false,
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : 'N/A'}
              </p>
            </div>
          </div>

          <Separator />

          {/* Actions */}
          <div className="flex gap-2">
            <Button className="flex-1" variant="default">
              Reserve Seat
            </Button>
            <Button variant="outline" className="flex-1">
              View History
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
