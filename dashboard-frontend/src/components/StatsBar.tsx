import { Stats } from '@/lib/api';

interface StatsBarProps {
  stats: Stats;
}

export function StatsBar({ stats }: StatsBarProps) {
  const statItems = [
    {
      label: 'Occupied',
      value: stats.occupied,
      color: '#ef4444',
      delay: '0ms',
    },
    {
      label: 'Available',
      value: stats.empty,
      color: '#22c55e',
      delay: '50ms',
    },
    {
      label: 'Ghost',
      value: stats.ghost,
      color: '#a855f7',
      delay: '100ms',
    },
    {
      label: 'Utilization',
      value: `${stats.utilization.toFixed(1)}%`,
      color: '#3b82f6',
      delay: '150ms',
      isPercent: true,
    },
  ];

  return (
    <>
      {statItems.map((item) => (
        <div
          key={item.label}
          className="card p-6 animate-fade-in"
          style={{
            animationDelay: item.delay,
          }}
        >
          <p className="text-sm font-medium text-white/50 mb-3">
            {item.label}
          </p>
          <p
            className="stat-value"
            style={{ color: item.color }}
          >
            {item.value}
          </p>
        </div>
      ))}
    </>
  );
}
