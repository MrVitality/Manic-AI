'use client'
export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
      <h2 className="text-lg font-semibold">Something went wrong</h2>
      <p className="text-sm text-gray-500">{error.message}</p>
      <button onClick={reset} className="px-4 py-2 rounded bg-blue-500 text-white hover:bg-blue-600">
        Try again
      </button>
    </div>
  )
}
