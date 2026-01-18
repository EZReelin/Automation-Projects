import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import {
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'

interface Alert {
  id: string
  assetId: string
  assetName: string
  severity: string
  title: string
  detectedAt: string
  status: string
}

const severityIcons = {
  critical: ExclamationCircleIcon,
  emergency: ExclamationCircleIcon,
  warning: ExclamationTriangleIcon,
  info: InformationCircleIcon,
}

export default function AlertsList({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No recent alerts
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {alerts.map((alert) => {
        const Icon = severityIcons[alert.severity as keyof typeof severityIcons] || InformationCircleIcon

        return (
          <Link
            key={alert.id}
            to={`/alerts?id=${alert.id}`}
            className={clsx(
              'block p-3 rounded-lg border transition-colors hover:bg-gray-50',
              alert.severity === 'critical' && 'border-red-200',
              alert.severity === 'warning' && 'border-yellow-200',
              alert.severity === 'info' && 'border-blue-200'
            )}
          >
            <div className="flex items-start gap-3">
              <div
                className={clsx(
                  'p-1.5 rounded-lg flex-shrink-0',
                  alert.severity === 'critical' && 'bg-red-100',
                  alert.severity === 'warning' && 'bg-yellow-100',
                  alert.severity === 'info' && 'bg-blue-100'
                )}
              >
                <Icon
                  className={clsx(
                    'w-4 h-4',
                    alert.severity === 'critical' && 'text-red-600',
                    alert.severity === 'warning' && 'text-yellow-600',
                    alert.severity === 'info' && 'text-blue-600'
                  )}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {alert.title}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {alert.assetName}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {formatDistanceToNow(new Date(alert.detectedAt), { addSuffix: true })}
                </p>
              </div>
              {alert.status === 'active' && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                  New
                </span>
              )}
            </div>
          </Link>
        )
      })}
    </div>
  )
}
