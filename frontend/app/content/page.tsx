import type { Metadata } from 'next'
import dynamic from 'next/dynamic'
import LoadingSkeleton from '@/components/LoadingSkeleton'

export const metadata: Metadata = { title: 'Content — Manic AI' }

const ContentCalendar = dynamic(() => import('@/components/ContentCalendar'), {
  loading: () => <LoadingSkeleton title="LOADING_CONTENT" rows={8} />,
})

export default function ContentPage() {
  return <ContentCalendar />
}
