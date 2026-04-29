import { useEffect, useState } from 'react'
import {
  Server, Github, Database, Layers, Bug, ExternalLink,
  Sparkles, Wifi, WifiOff,
} from 'lucide-react'
import api from '@/lib/api'

interface SkillRef {
  name: string
  source: string
  color?: string | null
  icon?: string | null
}

interface McpServer {
  id: string
  label: string
  kind: 'stdio' | 'sse' | 'streamable_http'
  description: string
  pack_id: string | null
  tool_filter?: string[] | null
  placeholder?: boolean
  connected: boolean
  skills: SkillRef[]
}

// Map a server id to a recognizable icon. New ids fall back to the
// generic Server icon — extend this map when you add a new MCP server
// type to the platform.
const SERVER_ICONS: Record<string, any> = {
  github: Github,
  jira: Bug,
  onelake: Database,
  exchange: Layers,
}

const KIND_LABEL: Record<McpServer['kind'], string> = {
  stdio: 'STDIO subprocess',
  sse: 'HTTP · Server-Sent Events',
  streamable_http: 'HTTP · Streamable',
}

export default function McpServersTab() {
  const [servers, setServers] = useState<McpServer[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setError(null)
    api.get<McpServer[]>('/api/mcp_servers')
      .then((r) => setServers(r.data))
      .catch((e) => {
        setError(e?.response?.data?.detail || 'Failed to load MCP servers.')
        setServers([])
      })
  }
  useEffect(load, [])

  if (servers === null) {
    return <div style={{ color: 'var(--text-muted)' }}>Loading MCP servers…</div>
  }

  return (
    <div>
      <div className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div>
          <div className="font-display text-base font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
            MCP Servers
          </div>
          <p className="text-xs max-w-2xl" style={{ color: 'var(--text-muted)' }}>
            Pack-registered Model Context Protocol servers the workbench can attach to. Each
            server's tool catalog is advertised to any skill that lists its id under
            <code style={mono}>mcp_servers:</code> in YAML frontmatter. Servers come up only
            when their <code style={mono}>CMA_MCP_*_URL</code> environment variable is set.
          </p>
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold"
          style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div
          className="text-xs px-3 py-2 rounded-md mb-4"
          style={{ background: 'var(--error-bg)', color: 'var(--error)' }}
        >
          {error}
        </div>
      )}

      {servers.length === 0 ? (
        <div
          className="panel text-center"
          style={{ padding: '40px 20px', borderStyle: 'dashed' }}
        >
          <Server size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            No MCP servers registered
          </div>
          <div className="text-xs mt-1 max-w-md mx-auto" style={{ color: 'var(--text-muted)' }}>
            Drop a pack under <code style={mono}>backend/packs/</code> that calls
            <code style={mono}> ctx.register_mcp_server(...) </code>and set the matching
            <code style={mono}> CMA_MCP_*_URL </code> env vars in <code style={mono}>backend/.env</code>.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {servers.map((s) => {
            const Icon = SERVER_ICONS[s.id] || Server
            return (
              <div
                key={s.id}
                className="panel"
                style={{ padding: 16, position: 'relative', overflow: 'hidden' }}
              >
                {/* Connection state pill — top right */}
                <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-0.5 rounded-md"
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    background: s.placeholder
                      ? 'rgba(217,119,6,0.12)'
                      : (s.connected ? 'var(--success-bg)' : 'var(--error-bg)'),
                    color: s.placeholder
                      ? '#D97706'
                      : (s.connected ? 'var(--success)' : 'var(--error)'),
                  }}
                  title={s.placeholder
                    ? 'Demo placeholder — appears in the UI but no client is constructed. Set the URL env var to flip it live.'
                    : s.connected
                      ? 'Server registered and client constructed.'
                      : 'Server registered but client failed to initialize.'}
                >
                  {s.placeholder
                    ? <Sparkles size={10} />
                    : (s.connected ? <Wifi size={10} /> : <WifiOff size={10} />)}
                  {s.placeholder ? 'Placeholder' : (s.connected ? 'Live' : 'Offline')}
                </div>

                <div className="flex items-start gap-3 mb-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                  >
                    <Icon size={18} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-base font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                      {s.label}
                    </div>
                    <div className="text-[11px] font-mono mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      {s.id} · {KIND_LABEL[s.kind] || s.kind}
                      {s.pack_id && (
                        <> · pack: <span style={{ color: 'var(--accent)' }}>{s.pack_id}</span></>
                      )}
                    </div>
                  </div>
                </div>

                {s.description && (
                  <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {s.description}
                  </p>
                )}

                {s.tool_filter && s.tool_filter.length > 0 && (
                  <div className="mb-3">
                    <div
                      className="text-[10px] font-semibold uppercase tracking-widest mb-1"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Allowlisted tools ({s.tool_filter.length})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {s.tool_filter.map((t) => (
                        <span
                          key={t}
                          className="px-1.5 py-0.5 rounded font-mono"
                          style={{
                            fontSize: 10,
                            background: 'var(--bg-elevated)',
                            border: '1px solid var(--border)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <div
                    className="text-[10px] font-semibold uppercase tracking-widest mb-1.5 flex items-center gap-1"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    <Sparkles size={10} />
                    Skills attached ({s.skills.length})
                  </div>
                  {s.skills.length === 0 ? (
                    <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      No skill currently attaches to this server. Add{' '}
                      <code style={mono}>mcp_servers: [{s.id}]</code> to a skill's frontmatter.
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {s.skills.map((sk) => (
                        <span
                          key={sk.name}
                          className="px-2 py-0.5 rounded-md text-[11px] font-semibold flex items-center gap-1"
                          style={{
                            background: sk.color ? `${sk.color}1A` : 'var(--accent-light)',
                            color: sk.color || 'var(--accent)',
                            border: `1px solid ${sk.color || 'var(--accent)'}`,
                          }}
                        >
                          {sk.name}
                          <span
                            className="font-mono"
                            style={{ fontSize: 9, opacity: 0.65, letterSpacing: '0.04em' }}
                          >
                            {sk.source}
                          </span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div
        className="mt-6 panel text-xs"
        style={{ padding: 12, color: 'var(--text-muted)', borderStyle: 'dashed' }}
      >
        <div className="flex items-start gap-2">
          <ExternalLink size={12} className="mt-0.5 shrink-0" />
          <span>
            Read-only view. To add or remove servers, edit the pack file under{' '}
            <code style={mono}>backend/packs/&lt;pack_id&gt;/pack.py</code> and restart the
            backend. Auth tokens stay in <code style={mono}>backend/.env</code> and never
            leave the server.
          </span>
        </div>
      </div>
    </div>
  )
}

const mono = {
  background: 'var(--bg-elevated)',
  padding: '0 4px',
  borderRadius: 3,
  fontSize: 10.5,
  fontFamily: 'JetBrains Mono, monospace',
  color: 'var(--accent)',
} as const
