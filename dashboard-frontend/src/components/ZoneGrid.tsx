import { Zone } from '@/lib/api';
import { Card } from './ui/card';
import { Progress } from './ui/progress';

interface ZoneGridProps {
  zones: Record<string, Zone>;
  zoneNames: string[];
}

export function ZoneGrid({ zones, zoneNames }: ZoneGridProps) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Zone Overview</h2>
        <span className="text-xs text-muted-foreground">7 zones</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {zoneNames.map((zoneName, index) => {
          const zone = zones[zoneName];
          const occupied = zone?.occupied || 0;
          const total = zone?.total || 4;
          const percentage = total > 0 ? (occupied / total) * 100 : 0;

          // Determine dominant state for styling
          let stateClass = 'empty';
          if (zone?.seats) {
            const states = Object.values(zone.seats).map(s => s.state);
            if (states.includes('confirmed')) stateClass = 'confirmed';
            else if (states.includes('suspected')) stateClass = 'suspected';
            else if (states.includes('occupied') && states.filter(s => s === 'occupied').length > total / 2) stateClass = 'occupied';
          }

          return (
            <div
              key={zoneName}
              className={`
                relative p-4 rounded-xl border transition-all duration-300
                hover:scale-[1.02] cursor-pointer animate-fade-in
                ${stateClass === 'confirmed' ? 'bg-purple-500/15 border-purple-500/30' :
                  stateClass === 'suspected' ? 'bg-yellow-500/15 border-yellow-500/30' :
                  stateClass === 'occupied' ? 'bg-red-500/15 border-red-500/30' :
                  'bg-green-500/10 border-green-500/20'}
              `}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">{zoneName}</span>
                <span className={`
                  text-xs px-2 py-0.5 rounded-full
                  ${stateClass === 'confirmed' ? 'bg-purple-500/30 text-purple-300' :
                    stateClass === 'suspected' ? 'bg-yellow-500/30 text-yellow-300' :
                    stateClass === 'occupied' ? 'bg-red-500/30 text-red-300' :
                    'bg-green-500/30 text-green-300'}
                `}>
                  {occupied}/{total}
                </span>
              </div>

              <Progress
                value={percentage}
                className={`
                  h-1.5
                  ${stateClass === 'confirmed' ? '[&>div]:bg-purple-500' :
                    stateClass === 'suspected' ? '[&>div]:bg-yellow-500' :
                    stateClass === 'occupied' ? '[&>div]:bg-red-500' :
                    '[&>div]:bg-green-500'}
                `}
              />

              <div className="mt-2 text-xs text-muted-foreground">
                {percentage.toFixed(0)}% occupied
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
