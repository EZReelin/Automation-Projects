import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { ExclamationTriangleIcon, ClockIcon } from '@heroicons/react/24/outline'

interface Asset {
  id: string
  name: string
  assetTag: string
  assetType: string
  status: string
  healthScore: number
  predictedRulDays: number | null
  location: string | null
}

const assetTypeLabels: Record<string, string> = {
  cnc_machining_center: 'CNC Mill',
  cnc_lathe: 'CNC Lathe',
  hydraulic_press: 'Hydraulic Press',
  press_brake: 'Press Brake',
  air_compressor: 'Air Compressor',
  shear: 'Shear',
  mig_welder: 'MIG Welder',
  tig_welder: 'TIG Welder',
}

function HealthBadge({ score, status }: { score: number; status: string }) {
  return (
    <div
      className={clsx(
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium',
        status === 'critical' && 'bg-red-100 text-red-800',
        status === 'warning' && 'bg-yellow-100 text-yellow-800',
        status === 'healthy' && 'bg-green-100 text-green-800',
        status === 'maintenance' && 'bg-blue-100 text-blue-800',
        status === 'offline' && 'bg-gray-100 text-gray-800'
      )}
    >
      <div
        className={clsx(
          'w-2 h-2 rounded-full',
          status === 'critical' && 'bg-red-500 health-pulse',
          status === 'warning' && 'bg-yellow-500',
          status === 'healthy' && 'bg-green-500',
          status === 'maintenance' && 'bg-blue-500',
          status === 'offline' && 'bg-gray-500'
        )}
      />
      {score.toFixed(0)}%
    </div>
  )
}

export default function AssetHealthGrid({ assets }: { assets: Asset[] }) {
  if (assets.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No assets requiring attention
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {assets.map((asset) => (
        <Link
          key={asset.id}
          to={`/assets/${asset.id}`}
          className={clsx(
            'block p-4 rounded-lg border transition-all hover:shadow-md',
            asset.status === 'critical' && 'border-red-200 bg-red-50',
            asset.status === 'warning' && 'border-yellow-200 bg-yellow-50',
            asset.status === 'healthy' && 'border-green-200 bg-green-50',
            asset.status === 'maintenance' && 'border-blue-200 bg-blue-50',
            asset.status === 'offline' && 'border-gray-200 bg-gray-50'
          )}
        >
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-medium text-gray-900">{asset.name}</h3>
              <p className="text-sm text-gray-500">
                {assetTypeLabels[asset.assetType] || asset.assetType}
              </p>
            </div>
            <HealthBadge score={asset.healthScore} status={asset.status} />
          </div>

          <div className="mt-3 flex items-center gap-4 text-sm">
            {asset.predictedRulDays !== null && (
              <div
                className={clsx(
                  'flex items-center gap-1',
                  asset.predictedRulDays <= 7 && 'text-red-600',
                  asset.predictedRulDays > 7 && asset.predictedRulDays <= 30 && 'text-yellow-600',
                  asset.predictedRulDays > 30 && 'text-gray-600'
                )}
              >
                <ClockIcon className="w-4 h-4" />
                {asset.predictedRulDays}d RUL
              </div>
            )}
            {asset.location && (
              <span className="text-gray-500">{asset.location}</span>
            )}
          </div>

          {asset.status === 'critical' && (
            <div className="mt-3 flex items-center gap-2 text-sm text-red-700">
              <ExclamationTriangleIcon className="w-4 h-4" />
              Immediate attention required
            </div>
          )}
        </Link>
      ))}
    </div>
  )
}
