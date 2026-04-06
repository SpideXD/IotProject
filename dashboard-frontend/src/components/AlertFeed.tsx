import { Alert } from '@/lib/api';
import { Card } from './ui/card';
import { Ghost, AlertTriangle, Check, X, Clock } from 'lucide-react';

interface AlertFeedProps {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
  onSnooze: (id: string) => void;
}

export function AlertFeed({ alerts, onAcknowledge, onResolve, onSnooze }: AlertFeedProps) {
  const getAlertClass = (type: string) => {
    if (type.includes('confirmed') || type.includes('ghost_confirmed')) {
      return 'ghost';
    }
    if (type.includes('suspected') || type.includes('ghost_suspected')) {
      return 'warning';
    }
    if (type.includes('critical')) {
      return 'critical';
    }
    return 'info';
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">Alerts</h2>
        <span className="text-xs text-white/40">
          {alerts.filter(a => !a.acknowledged).length} active
        </span>
      </div>

      <div className="space-y-2 max-h-[280px] overflow-y-auto pr-1">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-white/30">
            <Ghost className="w-6 h-6 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No alerts</p>
          </div>
        ) : (
          alerts.map((alert, index) => (
            <div
              key={alert.id}
              className={`
                alert-card animate-slide-in
                ${alert.acknowledged ? 'opacity-40' : ''}
                ${getAlertClass(alert.type)}
              `}
              style={{ animationDelay: `${index * 25}ms` }}
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5">
                  {alert.type.includes('ghost') ? (
                    <Ghost className="w-4 h-4 text-purple-400" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-yellow-400" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-white/5 text-white/70">
                      {alert.type.replace('_', ' ')}
                    </span>
                    <span className="text-xs text-white/40">
                      {alert.seat_id}
                    </span>
                  </div>

                  <p className="text-sm text-white/60 line-clamp-2">
                    {alert.message}
                  </p>

                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-white/40">
                      {formatTime(alert.timestamp)}
                    </span>
                    {alert.countdown > 0 && (
                      <span className="flex items-center gap-1 text-xs text-yellow-400">
                        <Clock className="w-3 h-3" />
                        {alert.countdown}s
                      </span>
                    )}
                  </div>
                </div>

                {!alert.acknowledged && (
                  <div className="flex gap-1">
                    <button
                      onClick={() => onAcknowledge(alert.id)}
                      className="w-7 h-7 rounded flex items-center justify-center text-green-400/60 hover:text-green-400 hover:bg-green-400/10 transition-colors"
                      title="Acknowledge"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => onSnooze(alert.id)}
                      className="w-7 h-7 rounded flex items-center justify-center text-yellow-400/60 hover:text-yellow-400 hover:bg-yellow-400/10 transition-colors"
                      title="Snooze 5min"
                    >
                      <Clock className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={() => onResolve(alert.id)}
                      className="w-7 h-7 rounded flex items-center justify-center text-red-400/60 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                      title="Resolve"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
