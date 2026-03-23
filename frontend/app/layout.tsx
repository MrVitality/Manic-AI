import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import AppShell from '@/components/AppShell'
import { ToastProvider } from '@/components/Toast'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const jetbrains = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'Manic AI',
  description: 'Chat with local AI models, manage documents, and more. Powered by Ollama.',
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.svg',
  },
  openGraph: {
    title: 'Manic AI',
    description: 'Full-stack AI platform with RAG capabilities',
    type: 'website',
    siteName: 'Manic AI',
  },
  twitter: {
    card: 'summary',
    title: 'Manic AI',
    description: 'Full-stack AI platform with RAG capabilities',
  },
}

// Inline script to set theme, accent color, and font size before first paint, avoiding flash
const themeInitScript = `
(function() {
  try {
    var stored = JSON.parse(localStorage.getItem('manic-ai-ui') || '{}');
    var settings = stored && stored.state && stored.state.settings;

    // Theme
    var theme = settings && settings.theme;
    if (theme === 'light' || theme === 'dark') {
      document.documentElement.setAttribute('data-theme', theme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
    }

    // Accent color
    var accentColors = {
      blue: '#3b82f6',
      indigo: '#818cf8',
      violet: '#a78bfa',
      purple: '#8b5cf6',
      emerald: '#10b981'
    };
    var accent = settings && settings.accentColor;
    if (accent && accentColors[accent]) {
      document.documentElement.style.setProperty('--accent-blue', accentColors[accent]);
      document.documentElement.style.setProperty('--accent-cyan', accentColors[accent]);
      document.documentElement.style.setProperty('--accent-primary', accentColors[accent]);
    }

    // Font size
    var fontSizes = { sm: '14px', base: '16px', lg: '18px' };
    var fs = settings && settings.fontSize;
    if (fs && fontSizes[fs]) {
      document.documentElement.style.fontSize = fontSizes[fs];
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
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-white focus:text-black focus:rounded"
        >
          Skip to main content
        </a>
        <ToastProvider>
          <AppShell>{children}</AppShell>
        </ToastProvider>
      </body>
    </html>
  )
}
