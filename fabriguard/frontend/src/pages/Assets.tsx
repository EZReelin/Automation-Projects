import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { MagnifyingGlassIcon, PlusIcon, FunnelIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

// Mock data
const mockAssets = [
  { id: '1', name: 'CNC Mill #1', assetTag: 'CNC-001', assetType: 'cnc_machining_center', status: 'critical', healthScore: 35, predictedRulDays: 5, location: 'Bay A', lastReading: '2024-01-15T10:30:00Z' },
  { id: '2', name: 'Hydraulic Press #3', assetTag: 'HP-003', assetType: 'hydraulic_press', status: 'warning', healthScore: 58, predictedRulDays: 18, location: 'Bay B', lastReading: '2024-01-15T10:28:00Z' },
  { id: '3', name: 'Air Compressor #1', assetTag: 'AC-001', assetType: 'air_compressor', status: 'warning', healthScore: 62, predictedRulDays: 25, location: 'Utility', lastReading: '2024-01-15T10:25:00Z' },
  { id: '4', name: 'CNC Lathe #2', assetTag: 'CNC-002', assetType: 'cnc_lathe', status: 'healthy', healthScore: 88, predictedRulDays: 120, location: 'Bay A', lastReading: '2024-01-15T10:30:00Z' },
  { id: '5', name: 'Press Brake #1', assetTag: 'PB-001', assetType: 'press_brake', status: 'healthy', healthScore: 92, predictedRulDays: 180, location: 'Bay C', lastReading: '2024-01-15T10:29:00Z' },
  { id: '6', name: 'CNC Mill #2', assetTag: 'CNC-003', assetType: 'cnc_machining_center', status: 'healthy', healthScore: 85, predictedRulDays: 95, location: 'Bay A', lastReading: '2024-01-15T10:30:00Z' },
  { id: '7', name: 'Shear #1', assetTag: 'SH-001', assetType: 'shear', status: 'offline', healthScore: 0, predictedRulDays: null, location: 'Bay D', lastReading: '2024-01-14T16:00:00Z' },
]

const assetTypeLabels: Record<string, string> = {
  cnc_machining_center: 'CNC Mill',
  cnc_lathe: 'CNC Lathe',
  hydraulic_press: 'Hydraulic Press',
  press_brake: 'Press Brake',
  air_compressor: 'Air Compressor',
  shear: 'Shear',
}

const statusColors = {
  healthy: 'bg-green-100 text-green-800',
  warning: 'bg-yellow-100 text-yellow-800',
  critical: 'bg-red-100 text-red-800',
  maintenance: 'bg-blue-100 text-blue-800',
  offline: 'bg-gray-100 text-gray-800',
}

export default function Assets() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')

  const { data: assets, isLoading } = useQuery({
    queryKey: ['assets', search, statusFilter],
    queryFn: async () => {
      // In production: const response = await assetsApi.list({ search, status: statusFilter })
      return mockAssets.filter(a => {
        const matchesSearch = !search ||
          a.name.toLowerCase().includes(search.toLowerCase()) ||
          a.assetTag.toLowerCase().includes(search.toLowerCase())
        const matchesStatus = !statusFilter || a.status === statusFilter
        return matchesSearch && matchesStatus
      })
    },
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Assets</h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitor and manage your equipment fleet
          </p>
        </div>
        <button className="btn btn-primary">
          <PlusIcon className="w-5 h-5 mr-2" />
          Add Asset
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search assets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input w-full sm:w-48"
        >
          <option value="">All Statuses</option>
          <option value="healthy">Healthy</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
          <option value="maintenance">Maintenance</option>
          <option value="offline">Offline</option>
        </select>
      </div>

      {/* Assets table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Asset
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Health
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  RUL
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Location
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto" />
                  </td>
                </tr>
              ) : assets?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                    No assets found
                  </td>
                </tr>
              ) : (
                assets?.map((asset) => (
                  <tr key={asset.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link to={`/assets/${asset.id}`} className="block">
                        <div className="text-sm font-medium text-gray-900 hover:text-primary-600">
                          {asset.name}
                        </div>
                        <div className="text-sm text-gray-500">{asset.assetTag}</div>
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {assetTypeLabels[asset.assetType] || asset.assetType}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={clsx('status-badge', statusColors[asset.status as keyof typeof statusColors])}>
                        {asset.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                          <div
                            className={clsx(
                              'h-2 rounded-full',
                              asset.healthScore >= 80 && 'bg-green-500',
                              asset.healthScore >= 50 && asset.healthScore < 80 && 'bg-yellow-500',
                              asset.healthScore < 50 && 'bg-red-500'
                            )}
                            style={{ width: `${asset.healthScore}%` }}
                          />
                        </div>
                        <span className="text-sm text-gray-600">{asset.healthScore}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {asset.predictedRulDays !== null ? (
                        <span className={clsx(
                          asset.predictedRulDays <= 7 && 'text-red-600 font-medium',
                          asset.predictedRulDays > 7 && asset.predictedRulDays <= 30 && 'text-yellow-600',
                          asset.predictedRulDays > 30 && 'text-gray-600'
                        )}>
                          {asset.predictedRulDays} days
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {asset.location}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
