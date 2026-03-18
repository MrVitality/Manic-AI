import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

const AdvancedSettings = dynamic(() => import('@/components/AdvancedSettings'), {
  loading: () => <LoadingSkeleton title="LOADING_SETTINGS" rows={6} />,
})

export default function SettingsPage() {
  return <AdvancedSettings />
}
