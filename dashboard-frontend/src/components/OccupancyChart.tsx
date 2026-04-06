import { HistoryPoint } from '@/lib/api';
import { Card } from './ui/card';
import { Badge } from './ui/badge';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface OccupancyChartProps {
  history: HistoryPoint[];
}

export function OccupancyChart({ history }: OccupancyChartProps) {
  const chartData = history.map(point => ({
    time: new Date(point.ts).toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
    }),
    Occupied: point.occupied,
    Empty: point.empty,
    Ghost: point.ghost,
  }));

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold">Occupancy Trend</h2>
        <Badge variant="outline" className="text-xs border-white/10 text-white/50">
          Last 60 min
        </Badge>
      </div>

      <div className="chart-container">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
                vertical={false}
              />
              <XAxis
                dataKey="time"
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#18181b',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px',
                  padding: '10px',
                }}
                labelStyle={{ color: '#f1f5f9', marginBottom: '4px' }}
                itemStyle={{ color: '#94a3b8' }}
              />
              <Legend
                wrapperStyle={{ paddingTop: '10px' }}
                formatter={(value) => (
                  <span className="text-xs text-white/50">{value}</span>
                )}
              />
              <Line
                type="monotone"
                dataKey="Occupied"
                stroke="#ef4444"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#ef4444' }}
              />
              <Line
                type="monotone"
                dataKey="Empty"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#22c55e' }}
              />
              <Line
                type="monotone"
                dataKey="Ghost"
                stroke="#a855f7"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#a855f7' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-white/30 text-sm">
            No historical data available
          </div>
        )}
      </div>
    </Card>
  );
}
