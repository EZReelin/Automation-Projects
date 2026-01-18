import { useParams, Link } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'

export default function AssetDetail() {
  const { id } = useParams()

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/assets" className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeftIcon className="w-5 h-5 text-gray-500" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Asset Details</h1>
          <p className="text-sm text-gray-500">Asset ID: {id}</p>
        </div>
      </div>

      <div className="card p-6">
        <p className="text-gray-500">
          Asset detail view with sensor data, health trends, alerts, and maintenance history.
          This page would show comprehensive information about the selected asset.
        </p>
      </div>
    </div>
  )
}
