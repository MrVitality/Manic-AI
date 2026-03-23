import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

export const metadata: Metadata = { title: 'Models — Manic AI' }

const ModelManager = dynamic(() => import('@/components/ModelManager'), {
  loading: () => <LoadingSkeleton title="LOADING_MODELS" rows={5} />,
})

export default function ModelsPage() {
  return <ModelManager />
}
