# AI Agent Frontend

A modern, responsive chat interface for interacting with local AI models through Ollama.

## Features

- 🤖 **Chat Interface** - Clean, modern chat UI with streaming responses
- 📝 **Markdown Support** - Full markdown rendering with syntax highlighting
- 💾 **Persistent History** - Conversations saved locally in browser storage
- ⚙️ **Configurable Settings** - Temperature, system prompts, and more
- 📱 **Responsive Design** - Works on desktop and mobile
- 🌙 **Dark Mode** - Easy on the eyes

## Quick Start

### Prerequisites

- Node.js 20+
- Ollama running with API accessible

### Development

```bash
# Install dependencies
npm install

# Create environment file
cp .env.example .env.local

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
# Build the application
npm run build

# Start production server
npm start
```

### Docker

```bash
# Build Docker image
docker build -t ai-frontend .

# Run container
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://ollama:11434 \
  ai-frontend
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Ollama API endpoint | `http://localhost:8080` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL (optional) | - |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (optional) | - |

### Settings

Access settings via the gear icon in the sidebar:

- **General Tab**
  - API URL configuration
  - Temperature slider (0-2)
  - Stream responses toggle

- **Models Tab**
  - View installed models
  - Model details (size, parameters)

- **Advanced Tab**
  - System prompt customization
  - Max response length
  - Default model selection

## Project Structure

```
ai-frontend/
├── app/
│   ├── globals.css      # Global styles + Tailwind
│   ├── layout.tsx       # Root layout
│   └── page.tsx         # Main page
├── components/
│   ├── ChatArea.tsx     # Main chat container
│   ├── MessageInput.tsx # Message input field
│   ├── MessageList.tsx  # Message display
│   ├── SettingsModal.tsx # Settings dialog
│   └── Sidebar.tsx      # Conversation sidebar
├── hooks/
│   ├── useChat.ts       # Chat functionality
│   └── useModels.ts     # Model management
├── lib/
│   ├── api.ts           # API utilities
│   └── store.ts         # Zustand state store
├── types/
│   └── index.ts         # TypeScript definitions
└── public/
    └── favicon.svg      # App icon
```

## Architecture

### State Management

Uses [Zustand](https://github.com/pmndrs/zustand) for state management with persistence:

- **Conversations** - Chat history with messages
- **Settings** - User preferences
- **UI State** - Loading, errors, selections

### API Communication

The `lib/api.ts` module handles:

- Streaming chat responses via fetch API
- Model listing and management
- Health checks
- Embedding generation (for RAG)

### Styling

- [Tailwind CSS](https://tailwindcss.com/) for utility-first styling
- [@tailwindcss/typography](https://tailwindcss.com/docs/typography-plugin) for prose styling
- Custom scrollbar and animation styles

## Integration

### With Ollama

The frontend connects to Ollama's API for:

- `/api/tags` - List available models
- `/api/chat` - Send chat messages (streaming)
- `/api/embeddings` - Generate embeddings (for RAG)

### With Supabase (Optional)

When configured, enables:

- User authentication
- Cloud conversation storage
- RAG document storage

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift + Enter` | New line in message |

## Troubleshooting

### Cannot connect to Ollama

1. Verify Ollama is running: `ollama list`
2. Check CORS settings if using a proxy
3. Verify `NEXT_PUBLIC_API_URL` is correct

### Models not loading

1. Ensure at least one model is pulled: `ollama pull llama3.2`
2. Check browser console for API errors
3. Verify network connectivity

### Conversations not persisting

1. Check browser local storage is enabled
2. Clear storage and refresh: `localStorage.removeItem('ai-chat-storage')`

## Development

### Adding New Features

1. Create component in `components/`
2. Add types to `types/index.ts`
3. Update store in `lib/store.ts` if needed
4. Add API calls to `lib/api.ts`

### Code Style

- TypeScript strict mode enabled
- ESLint with Next.js config
- Prettier for formatting (optional)

## License

MIT

## Credits

Built with:

- [Next.js 14](https://nextjs.org/)
- [React 18](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Zustand](https://github.com/pmndrs/zustand)
- [React Markdown](https://github.com/remarkjs/react-markdown)
- [React Syntax Highlighter](https://github.com/react-syntax-highlighter/react-syntax-highlighter)
