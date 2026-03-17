'use client'

import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

const RagCenter = dynamic(() => import('@/components/RagCenter'), {
  loading: () => <LoadingSkeleton title="LOADING_RAG_CENTER" rows={5} />,
})

export default function RagPage() {
  return <RagCenter />
}
