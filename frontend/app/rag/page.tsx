'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

const RagCenter = dynamic(() => import('@/components/RagCenter'), {
  loading: () => <LoadingSkeleton title="LOADING_RAG_CENTER" rows={5} />,
})

export default function RagPage() {
  useEffect(() => { document.title = 'RAG Center — Manic AI' }, [])
  return <RagCenter />
}
