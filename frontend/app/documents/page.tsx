import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

export const metadata: Metadata = { title: 'Documents — Manic AI' }

const DocumentManager = dynamic(() => import('@/components/DocumentManager'), {
  loading: () => <LoadingSkeleton title="LOADING_DOCUMENTS" rows={5} />,
})

export default function DocumentsPage() {
  return <DocumentManager />
}
