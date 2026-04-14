import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

export const metadata: Metadata = { title: 'Leads — Manic AI' }

const LeadsManager = dynamic(() => import('@/components/LeadsManager'), {
  loading: () => <LoadingSkeleton title="LOADING_LEADS" rows={8} />,
})

export default function LeadsPage() {
  return <LeadsManager />
}
