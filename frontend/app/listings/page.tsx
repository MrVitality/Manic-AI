import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

export const metadata: Metadata = { title: 'Listings — Manic AI' }

const ListingsManager = dynamic(() => import('@/components/ListingsManager'), {
  loading: () => <LoadingSkeleton title="LOADING_LISTINGS" rows={8} />,
})

export default function ListingsPage() {
  return <ListingsManager />
}
