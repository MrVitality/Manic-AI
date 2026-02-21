'use client'

interface FlowNode {
  id: string
  label: string
  subtitle?: string
  status?: 'active' | 'idle' | 'error'
  x: number
  y: number
}

interface FlowEdge {
  from: string
  to: string
}

interface FlowDiagramProps {
  nodes: FlowNode[]
  edges: FlowEdge[]
  width?: number
  height?: number
  className?: string
}

const statusColors: Record<string, string> = {
  active: '#10b981',
  idle: '#6b7280',
  error: '#ef4444',
}

export default function FlowDiagram({ nodes, edges, width = 700, height = 200, className = '' }: FlowDiagramProps) {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const nodeW = 130
  const nodeH = 56

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={`w-full ${className}`} style={{ height }}>
      <defs>
        <marker id="flow-arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <path d="M0,0 L8,3 L0,6" fill="var(--accent-blue)" opacity="0.6" />
        </marker>
      </defs>

      {edges.map((edge, i) => {
        const from = nodeMap.get(edge.from)
        const to = nodeMap.get(edge.to)
        if (!from || !to) return null

        const x1 = from.x + nodeW
        const y1 = from.y + nodeH / 2
        const x2 = to.x
        const y2 = to.y + nodeH / 2
        const cpx = (x1 + x2) / 2

        return (
          <g key={i}>
            <path
              d={`M${x1},${y1} C${cpx},${y1} ${cpx},${y2} ${x2},${y2}`}
              fill="none"
              stroke="var(--accent-blue)"
              strokeWidth="2"
              strokeDasharray="6 4"
              opacity="0.4"
              markerEnd="url(#flow-arrow)"
            >
              <animate
                attributeName="stroke-dashoffset"
                from="10"
                to="0"
                dur="1.5s"
                repeatCount="indefinite"
              />
            </path>
            <circle r="3" fill="var(--accent-cyan)" opacity="0.8">
              <animateMotion
                dur="3s"
                repeatCount="indefinite"
                path={`M${x1},${y1} C${cpx},${y1} ${cpx},${y2} ${x2},${y2}`}
              />
            </circle>
          </g>
        )
      })}

      {nodes.map((node) => (
        <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
          <rect
            width={nodeW}
            height={nodeH}
            rx="10"
            fill="var(--bg-elevated)"
            stroke="var(--glass-border)"
            strokeWidth="1"
          />
          <circle
            cx={nodeW - 12}
            cy={12}
            r="4"
            fill={statusColors[node.status || 'idle']}
          >
            {node.status === 'active' && (
              <animate attributeName="opacity" values="1;0.4;1" dur="2s" repeatCount="indefinite" />
            )}
          </circle>
          <text
            x={nodeW / 2}
            y={24}
            textAnchor="middle"
            fill="var(--text-primary)"
            fontSize="12"
            fontWeight="600"
          >
            {node.label}
          </text>
          {node.subtitle && (
            <text
              x={nodeW / 2}
              y={42}
              textAnchor="middle"
              fill="var(--text-muted)"
              fontSize="10"
            >
              {node.subtitle}
            </text>
          )}
        </g>
      ))}
    </svg>
  )
}
