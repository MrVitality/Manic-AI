import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import AppShell from '@/components/AppShell'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const jetbrains = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'Manic AI',
  description: 'Chat with local AI models, manage documents, and more. Powered by Ollama.',
  icons: {
    icon: '/favicon.svg',
  },
}

// Inline script to set theme before first paint, avoiding flash
const themeInitScript = `
(function() {
  try {
    var stored = JSON.parse(localStorage.getItem('manic-ai-storage') || '{}');
    var theme = stored && stored.state && stored.state.settings && stored.state.settings.theme;
    if (theme === 'light' || theme === 'dark') {
      document.documentElement.setAttribute('data-theme', theme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch(e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body suppressHydrationWarning className={`${inter.variable} ${jetbrains.variable} font-sans antialiased`} style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  )
}
