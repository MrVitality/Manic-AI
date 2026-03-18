import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

const ModelManager = dynamic(() => import('@/components/ModelManager'), {
  loading: () => <LoadingSkeleton title="LOADING_MODELS" rows={5} />,
})

export default function ModelsPage() {
  return <ModelManager />
}
