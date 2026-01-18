import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts'

interface FleetHealthData {
  totalAssets: number
  healthyCount: number
  warningCount: number
  criticalCount: number
  offlineCount: number
  maintenanceCount: number
  avgHealthScore: number
}

const COLORS = {
  healthy: '#22c55e',
  warning: '#eab308',
  critical: '#ef4444',
  maintenance: '#3b82f6',
  offline: '#6b7280',
}

export default function FleetHealthChart({ data }: { data: FleetHealthData }) {
  const chartData = [
    { name: 'Healthy', value: data.healthyCount, color: COLORS.healthy },
    { name: 'Warning', value: data.warningCount, color: COLORS.warning },
    { name: 'Critical', value: data.criticalCount, color: COLORS.critical },
    { name: 'Maintenance', value: data.maintenanceCount, color: COLORS.maintenance },
    { name: 'Offline', value: data.offlineCount, color: COLORS.offline },
  ].filter(item => item.value > 0)

  return (
    <div className="flex flex-col md:flex-row items-center gap-8">
      {/* Pie chart */}
      <div className="w-full md:w-1/2 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [`${value} assets`, '']}
              contentStyle={{
                backgroundColor: '#1f2937',
                border: 'none',
                borderRadius: '8px',
                color: '#f9fafb',
              }}
            />
            <Legend
              verticalAlign="middle"
              align="right"
              layout="vertical"
              formatter={(value) => (
                <span className="text-sm text-gray-700">{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Health score display */}
      <div className="w-full md:w-1/2 flex flex-col items-center justify-center">
        <div className="relative">
          <svg className="w-40 h-40" viewBox="0 0 100 100">
            {/* Background circle */}
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke="#e5e7eb"
              strokeWidth="8"
            />
            {/* Progress circle */}
            <circle
              cx="50"
              cy="50"
              r="45"
              fill="none"
              stroke={
                data.avgHealthScore >= 80
                  ? COLORS.healthy
                  : data.avgHealthScore >= 50
                  ? COLORS.warning
                  : COLORS.critical
              }
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${(data.avgHealthScore / 100) * 283} 283`}
              transform="rotate(-90 50 50)"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-bold text-gray-900">
              {data.avgHealthScore.toFixed(0)}
            </span>
            <span className="text-sm text-gray-500">Health Score</span>
          </div>
        </div>
        <p className="mt-4 text-sm text-gray-600 text-center">
          {data.totalAssets} total assets monitored
        </p>
      </div>
    </div>
  )
}
