import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

const Dashboard = dynamic(() => import('@/components/Dashboard'), {
  loading: () => <LoadingSkeleton title="LOADING_DASHBOARD" rows={6} />,
})

export default function DashboardPage() {
  return <Dashboard />
}
