'use client'

import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

const DocumentManager = dynamic(() => import('@/components/DocumentManager'), {
  loading: () => <LoadingSkeleton title="LOADING_DOCUMENTS" rows={5} />,
})

export default function DocumentsPage() {
  return <DocumentManager />
}
