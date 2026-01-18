import { useQuery } from '@tanstack/react-query'
import {
  CpuChipIcon,
  BellAlertIcon,
  ClipboardDocumentListIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'
import clsx from 'clsx'
import FleetHealthChart from '../components/FleetHealthChart'
import AssetHealthGrid from '../components/AssetHealthGrid'
import AlertsList from '../components/AlertsList'
import api from '../services/api'

interface DashboardData {
  fleetHealth: {
    totalAssets: number
    healthyCount: number
    warningCount: number
    criticalCount: number
    offlineCount: number
    maintenanceCount: number
    avgHealthScore: number
    assetsRequiringAttention: number
  }
  alerts: {
    activeAlerts: number
    criticalAlerts: number
    warningAlerts: number
    unacknowledged: number
    alertsToday: number
    alertsThisWeek: number
  }
  workOrders: {
    openWorkOrders: number
    inProgress: number
    overdue: number
    completedThisMonth: number
    avgCompletionTimeHours: number
  }
  roi: {
    totalDowntimeAvoidedHours: number
    totalCostAvoided: number
    totalMaintenanceCost: number
    netSavings: number
    predictedFailuresCaught: number
    falsePositiveRate: number
    periodDays: number
  }
  assetsByHealth: Array<{
    id: string
    name: string
    assetTag: string
    assetType: string
    status: string
    healthScore: number
    predictedRulDays: number | null
    location: string | null
  }>
  recentAlerts: Array<{
    id: string
    assetId: string
    assetName: string
    severity: string
    title: string
    detectedAt: string
    status: string
  }>
}

// Mock data for demo
const mockDashboardData: DashboardData = {
  fleetHealth: {
    totalAssets: 24,
    healthyCount: 18,
    warningCount: 4,
    criticalCount: 1,
    offlineCount: 1,
    maintenanceCount: 0,
    avgHealthScore: 82.5,
    assetsRequiringAttention: 5,
  },
  alerts: {
    activeAlerts: 7,
    criticalAlerts: 1,
    warningAlerts: 4,
    unacknowledged: 3,
    alertsToday: 2,
    alertsThisWeek: 12,
  },
  workOrders: {
    openWorkOrders: 5,
    inProgress: 2,
    overdue: 1,
    completedThisMonth: 8,
    avgCompletionTimeHours: 4.5,
  },
  roi: {
    totalDowntimeAvoidedHours: 156,
    totalCostAvoided: 780000,
    totalMaintenanceCost: 45000,
    netSavings: 735000,
    predictedFailuresCaught: 12,
    falsePositiveRate: 0.08,
    periodDays: 30,
  },
  assetsByHealth: [
    { id: '1', name: 'CNC Mill #1', assetTag: 'CNC-001', assetType: 'cnc_machining_center', status: 'critical', healthScore: 35, predictedRulDays: 5, location: 'Bay A' },
    { id: '2', name: 'Hydraulic Press #3', assetTag: 'HP-003', assetType: 'hydraulic_press', status: 'warning', healthScore: 58, predictedRulDays: 18, location: 'Bay B' },
    { id: '3', name: 'Air Compressor #1', assetTag: 'AC-001', assetType: 'air_compressor', status: 'warning', healthScore: 62, predictedRulDays: 25, location: 'Utility' },
    { id: '4', name: 'CNC Lathe #2', assetTag: 'CNC-002', assetType: 'cnc_lathe', status: 'healthy', healthScore: 88, predictedRulDays: 120, location: 'Bay A' },
    { id: '5', name: 'Press Brake #1', assetTag: 'PB-001', assetType: 'press_brake', status: 'healthy', healthScore: 92, predictedRulDays: 180, location: 'Bay C' },
  ],
  recentAlerts: [
    { id: 'a1', assetId: '1', assetName: 'CNC Mill #1', severity: 'critical', title: 'Spindle bearing showing severe wear patterns', detectedAt: '2024-01-15T10:30:00Z', status: 'active' },
    { id: 'a2', assetId: '2', assetName: 'Hydraulic Press #3', severity: 'warning', title: 'Pump pressure degradation detected', detectedAt: '2024-01-15T08:15:00Z', status: 'acknowledged' },
    { id: 'a3', assetId: '3', assetName: 'Air Compressor #1', severity: 'warning', title: 'Filter differential pressure elevated', detectedAt: '2024-01-14T16:45:00Z', status: 'active' },
  ],
}

function StatCard({
  title,
  value,
  subValue,
  icon: Icon,
  trend,
  trendDirection,
  href,
}: {
  title: string
  value: string | number
  subValue?: string
  icon: React.ElementType
  trend?: string
  trendDirection?: 'up' | 'down' | 'neutral'
  href?: string
}) {
  const content = (
    <div className="card p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="mt-1 text-3xl font-semibold text-gray-900">{value}</p>
          {subValue && (
            <p className="mt-1 text-sm text-gray-500">{subValue}</p>
          )}
          {trend && (
            <div className="mt-2 flex items-center text-sm">
              {trendDirection === 'up' && (
                <ArrowTrendingUpIcon className="w-4 h-4 mr-1 text-green-500" />
              )}
              {trendDirection === 'down' && (
                <ArrowTrendingDownIcon className="w-4 h-4 mr-1 text-red-500" />
              )}
              <span
                className={clsx(
                  trendDirection === 'up' && 'text-green-600',
                  trendDirection === 'down' && 'text-red-600',
                  trendDirection === 'neutral' && 'text-gray-600'
                )}
              >
                {trend}
              </span>
            </div>
          )}
        </div>
        <div className="p-3 bg-primary-50 rounded-xl">
          <Icon className="w-6 h-6 text-primary-600" />
        </div>
      </div>
    </div>
  )

  if (href) {
    return <Link to={href}>{content}</Link>
  }
  return content
}

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      // In production, fetch from API
      // const response = await api.get('/dashboard/overview')
      // return response.data
      return mockDashboardData
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (!data) return null

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Fleet health overview and predictive maintenance insights
        </p>
      </div>

      {/* Critical alert banner */}
      {data.alerts.criticalAlerts > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center">
          <ExclamationTriangleIcon className="w-6 h-6 text-red-600 mr-3 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-medium text-red-800">
              {data.alerts.criticalAlerts} Critical Alert{data.alerts.criticalAlerts > 1 ? 's' : ''} Require Immediate Attention
            </h3>
            <p className="mt-1 text-sm text-red-700">
              Equipment failures predicted within 7 days. Review and take action.
            </p>
          </div>
          <Link
            to="/alerts?severity=critical"
            className="btn btn-danger ml-4"
          >
            View Alerts
          </Link>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Fleet Health Score"
          value={`${data.fleetHealth.avgHealthScore.toFixed(0)}%`}
          subValue={`${data.fleetHealth.totalAssets} total assets`}
          icon={CpuChipIcon}
          trend={`${data.fleetHealth.assetsRequiringAttention} need attention`}
          trendDirection={data.fleetHealth.assetsRequiringAttention > 0 ? 'down' : 'up'}
          href="/assets"
        />
        <StatCard
          title="Active Alerts"
          value={data.alerts.activeAlerts}
          subValue={`${data.alerts.unacknowledged} unacknowledged`}
          icon={BellAlertIcon}
          trend={`${data.alerts.alertsToday} today`}
          trendDirection="neutral"
          href="/alerts"
        />
        <StatCard
          title="Open Work Orders"
          value={data.workOrders.openWorkOrders}
          subValue={`${data.workOrders.inProgress} in progress`}
          icon={ClipboardDocumentListIcon}
          trend={data.workOrders.overdue > 0 ? `${data.workOrders.overdue} overdue` : 'None overdue'}
          trendDirection={data.workOrders.overdue > 0 ? 'down' : 'up'}
          href="/work-orders"
        />
        <StatCard
          title="Cost Avoided (30d)"
          value={formatCurrency(data.roi.totalCostAvoided)}
          subValue={`${data.roi.totalDowntimeAvoidedHours}h downtime avoided`}
          icon={CurrencyDollarIcon}
          trend={`${data.roi.predictedFailuresCaught} failures caught`}
          trendDirection="up"
          href="/reports"
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Fleet health chart */}
        <div className="lg:col-span-2">
          <div className="card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Fleet Health Distribution
            </h2>
            <FleetHealthChart data={data.fleetHealth} />
          </div>
        </div>

        {/* Recent alerts */}
        <div className="lg:col-span-1">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Recent Alerts
              </h2>
              <Link
                to="/alerts"
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                View all
              </Link>
            </div>
            <AlertsList alerts={data.recentAlerts} />
          </div>
        </div>
      </div>

      {/* Assets requiring attention */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Assets Requiring Attention
          </h2>
          <Link
            to="/assets?status=warning,critical"
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            View all assets
          </Link>
        </div>
        <AssetHealthGrid
          assets={data.assetsByHealth.filter(
            (a) => a.status === 'warning' || a.status === 'critical'
          )}
        />
      </div>
    </div>
  )
}
