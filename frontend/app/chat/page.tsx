'use client'

import { useEffect } from 'react'
import ChatArea from '@/components/ChatArea'

export default function ChatPage() {
  useEffect(() => { document.title = 'Chat — Manic AI' }, [])
  return <ChatArea />
}
