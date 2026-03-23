'use client'

import { useMemo } from 'react'

interface GraphNode {
  id: string
  label: string
  x: number
  y: number
  radius: number
  color: string
}

interface GraphEdge {
  from: GraphNode
  to: GraphNode
}

const EXAMPLE_NODES: Omit<GraphNode, 'color'>[] = [
  { id: 'doc-1', label: 'AI Research', x: 180, y: 140, radius: 28 },
  { id: 'doc-2', label: 'Neural Nets', x: 340, y: 90, radius: 22 },
  { id: 'doc-3', label: 'Transformers', x: 490, y: 150, radius: 26 },
  { id: 'doc-4', label: 'RAG Systems', x: 280, y: 270, radius: 30 },
  { id: 'doc-5', label: 'Embeddings', x: 450, y: 290, radius: 24 },
  { id: 'doc-6', label: 'Vector DBs', x: 610, y: 200, radius: 20 },
  { id: 'doc-7', label: 'Fine-tuning', x: 100, y: 310, radius: 18 },
  { id: 'doc-8', label: 'LLM Agents', x: 580, y: 370, radius: 22 },
]

const EDGE_PAIRS: [string, string][] = [
  ['doc-1', 'doc-2'],
  ['doc-1', 'doc-4'],
  ['doc-2', 'doc-3'],
  ['doc-3', 'doc-5'],
  ['doc-3', 'doc-6'],
  ['doc-4', 'doc-5'],
  ['doc-4', 'doc-7'],
  ['doc-5', 'doc-8'],
  ['doc-6', 'doc-8'],
]

const NODE_COLORS = [
  'var(--accent-blue)',
  'var(--accent-cyan)',
  'var(--accent-purple)',
  'var(--accent-emerald)',
]

const DOT_GRID_PATTERN_ID = 'rag-graph-dot-grid'

export default function RagGraph() {
  const nodes: GraphNode[] = useMemo(
    () =>
      EXAMPLE_NODES.map((n, i) => ({
        ...n,
        color: NODE_COLORS[i % NODE_COLORS.length],
      })),
    [],
  )

  const nodeMap = useMemo(
    () => new Map(nodes.map((n) => [n.id, n])),
    [nodes],
  )

  const edges: GraphEdge[] = useMemo(
    () =>
      EDGE_PAIRS.flatMap(([fromId, toId]) => {
        const from = nodeMap.get(fromId)
        const to = nodeMap.get(toId)
        return from && to ? [{ from, to }] : []
      }),
    [nodeMap],
  )

  return (
    <div className="space-y-6">
      {/* Description card */}
      <div
        className="p-4 rounded-xl text-sm"
        style={{
          background: 'var(--glass-bg)',
          border: '1px solid var(--glass-border)',
          color: 'var(--text-secondary)',
        }}
      >
        <p className="mb-1 font-medium" style={{ color: 'var(--text-primary)' }}>
          Knowledge Graph Visualization
        </p>
        <p style={{ color: 'var(--text-muted)' }}>
          Connect entities across your documents. Coming soon: entity extraction at ingest time.
        </p>
      </div>

      {/* SVG canvas */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          border: '1px solid var(--glass-border)',
          background: 'var(--bg-secondary)',
        }}
      >
        <svg
          width="100%"
          viewBox="0 0 800 500"
          style={{ display: 'block', maxHeight: '500px' }}
          aria-label="Knowledge graph placeholder"
          role="img"
        >
          <defs>
            <pattern
              id={DOT_GRID_PATTERN_ID}
              x="0"
              y="0"
              width="24"
              height="24"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r="1" fill="rgba(255,255,255,0.04)" />
            </pattern>
          </defs>

          {/* Dot-grid background */}
          <rect width="800" height="500" fill={`url(#${DOT_GRID_PATTERN_ID})`} />

          {/* Edges */}
          {edges.map((edge, i) => (
            <line
              key={i}
              x1={edge.from.x}
              y1={edge.from.y}
              x2={edge.to.x}
              y2={edge.to.y}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
          ))}

          {/* Nodes */}
          {nodes.map((node) => (
            <g key={node.id}>
              {/* Glow halo */}
              <circle
                cx={node.x}
                cy={node.y}
                r={node.radius + 6}
                fill={node.color}
                opacity="0.08"
              />
              {/* Main circle */}
              <circle
                cx={node.x}
                cy={node.y}
                r={node.radius}
                fill={node.color}
                opacity="0.18"
                stroke={node.color}
                strokeWidth="1.5"
                strokeOpacity="0.6"
              />
              {/* Label */}
              <text
                x={node.x}
                y={node.y + node.radius + 14}
                textAnchor="middle"
                fontSize="10"
                fill="rgba(255,255,255,0.55)"
                fontFamily="ui-monospace, monospace"
              >
                {node.label}
              </text>
            </g>
          ))}

          {/* Center label */}
          <text
            x="400"
            y="470"
            textAnchor="middle"
            fontSize="11"
            fill="rgba(255,255,255,0.2)"
            fontFamily="ui-monospace, monospace"
            letterSpacing="0.08em"
          >
            ENTITY GRAPH — COMING SOON
          </text>
        </svg>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Documents', value: '--' },
          { label: 'Entities', value: '--' },
          { label: 'Connections', value: '--' },
          { label: 'Clusters', value: '--' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl p-3 text-center"
            style={{
              background: 'var(--glass-bg)',
              border: '1px solid var(--glass-border)',
            }}
          >
            <div
              className="text-xl font-bold font-mono mb-0.5"
              style={{ color: 'var(--accent-cyan)' }}
            >
              {stat.value}
            </div>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
