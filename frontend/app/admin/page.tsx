import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

export const metadata: Metadata = { title: 'Admin — Manic AI' }

const AdminDashboard = dynamic(() => import('@/components/AdminDashboard'), {
  loading: () => <LoadingSkeleton title="LOADING_ADMIN" rows={6} />,
})

export default function AdminPage() {
  return <AdminDashboard />
}
