import { useEffect, useRef, useState } from 'react'
import { Send, Sparkles, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChatStore } from '@/store/chatStore'
import api from '@/lib/api'
import { cn } from '@/lib/utils'

interface ChatPanelProps {
  open: boolean
  onClose: () => void
}

const mdComponents: any = {
  h1: (p: any) => (
    <h1
      style={{
        color: 'var(--text-primary)', fontSize: 14, fontWeight: 700, marginTop: 12, marginBottom: 5,
        borderBottom: '1px solid var(--border)', paddingBottom: 4,
      }}
      {...p}
    />
  ),
  h2: (p: any) => (
    <h2 style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 600, marginTop: 10, marginBottom: 4 }} {...p} />
  ),
  h3: (p: any) => (
    <h3 style={{ color: 'var(--accent)', fontSize: 12, fontWeight: 600, marginTop: 8, marginBottom: 3 }} {...p} />
  ),
  p: (p: any) => <p style={{ margin: '3px 0', lineHeight: 1.6, fontSize: 12 }} {...p} />,
  ul: (p: any) => <ul style={{ paddingLeft: 16, margin: '3px 0', fontSize: 12 }} {...p} />,
  ol: (p: any) => <ol style={{ paddingLeft: 16, margin: '3px 0', fontSize: 12 }} {...p} />,
  li: (p: any) => <li style={{ marginBottom: 2, lineHeight: 1.5, fontSize: 12 }} {...p} />,
  strong: (p: any) => {
    const content = String(p.children || '')
    if (/(WARN|EXCEED|BREACH|ALERT)/i.test(content))
      return (
        <strong
          style={{
            color: 'var(--error)', fontWeight: 700, background: 'rgba(220,38,38,0.08)',
            padding: '1px 3px', borderRadius: 3, fontSize: 12,
          }}
          {...p}
        />
      )
    if (/(WITHIN|PASS|OK)/i.test(content))
      return <strong style={{ color: 'var(--success)', fontWeight: 700, fontSize: 12 }} {...p} />
    if (/\$|\d+(\.\d+)?[BMK]|\d+ bps/.test(content))
      return (
        <strong
          style={{
            color: 'var(--accent)', fontWeight: 700,
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
          }}
          {...p}
        />
      )
    return <strong style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 12 }} {...p} />
  },
  em: (p: any) => <em style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: 12 }} {...p} />,
  code: (p: any) => (
    <code
      style={{
        color: 'var(--accent)', background: 'rgba(0,73,119,0.06)',
        padding: '1px 4px', borderRadius: 3, fontSize: 11,
        fontFamily: 'JetBrains Mono, monospace',
      }}
      {...p}
    />
  ),
  table: (p: any) => (
    <table style={{ width: '100%', borderCollapse: 'collapse', margin: '6px 0', fontSize: 11 }} {...p} />
  ),
  th: (p: any) => (
    <th
      style={{
        border: '1px solid var(--border)', padding: '4px 6px',
        color: '#fff', background: 'var(--accent)', fontWeight: 600,
        fontSize: 10, textTransform: 'uppercase' as const, letterSpacing: '0.04em',
      }}
      {...p}
    />
  ),
  td: (p: any) => (
    <td
      style={{
        border: '1px solid var(--border)', padding: '3px 6px',
        fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
      }}
      {...p}
    />
  ),
  blockquote: (p: any) => (
    <blockquote
      style={{
        borderLeft: '3px solid var(--accent)',
        background: 'rgba(0,73,119,0.03)',
        paddingLeft: 10, paddingTop: 4, paddingBottom: 4, paddingRight: 6,
        margin: '6px 0', borderRadius: '0 4px 4px 0', fontSize: 12,
        color: 'var(--text-secondary)',
      }}
      {...p}
    />
  ),
  hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '8px 0' }} />,
}

const QUICK_QUERIES = ['Brief me', 'Explain a metric', 'Risk alerts', 'Run a scenario', 'Draft report']

export default function ChatPanel({ open, onClose }: ChatPanelProps) {
  const messages = useChatStore((s) => s.messages)
  const isLoading = useChatStore((s) => s.isLoading)
  const pageContext = useChatStore((s) => s.pageContext)
  const functionId = useChatStore((s) => s.functionId)
  const addMessage = useChatStore((s) => s.addMessage)
  const setLoading = useChatStore((s) => s.setLoading)

  const [input, setInput] = useState('')
  const [panelWidth, setPanelWidth] = useState(400)
  const isDragging = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (detail && typeof detail === 'string') sendMessage(detail)
    }
    window.addEventListener('cma-chat', handler)
    return () => window.removeEventListener('cma-chat', handler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageContext, functionId])

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    const startX = e.clientX
    const startWidth = panelWidth
    const onMove = (ev: MouseEvent) => {
      if (!isDragging.current) return
      const delta = startX - ev.clientX
      setPanelWidth(Math.max(340, Math.min(720, startWidth + delta)))
    }
    const onUp = () => {
      isDragging.current = false
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  const sendMessage = async (content: string) => {
    if (!content.trim()) return
    addMessage({ role: 'user', content, timestamp: new Date().toISOString() })
    setInput('')
    setLoading(true)
    try {
      const ctxBundle = pageContext ? `[Context: ${pageContext}]\n\n${content}` : content
      const res = await api.post('/api/chat/message', {
        message: ctxBundle,
        function_id: functionId,
        agent_id: 'orchestrator',
      })
      addMessage({
        role: 'assistant',
        content: res.data.response || JSON.stringify(res.data),
        timestamp: new Date().toISOString(),
      })
    } catch {
      addMessage({
        role: 'assistant',
        content: 'Sorry — I could not reach the agent. Please try again.',
        timestamp: new Date().toISOString(),
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  if (!open) return null

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        style={{ background: 'rgba(11,15,25,0.30)' }}
        onClick={onClose}
      />
      <div
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col"
        style={{
          width: panelWidth,
          background: 'var(--bg-card)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-8px 0 40px rgba(0,0,0,0.10)',
        }}
      >
        <div
          onMouseDown={handleMouseDown}
          className="absolute left-0 top-0 bottom-0 z-10"
          style={{ width: 5, cursor: 'col-resize' }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = 'var(--accent)')}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
        />

        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{
            background: 'linear-gradient(135deg, var(--accent), var(--teal))',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(255,255,255,0.20)' }}
            >
              <Sparkles size={14} color="#fff" />
            </div>
            <div>
              <div className="font-display text-sm font-semibold" style={{ color: '#fff' }}>
                CMA Agent
              </div>
              <div
                className="font-mono"
                style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)' }}
              >
                {functionId ? functionId.replace(/_/g, ' ') : 'self-serve'} · auto-routing
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: 'rgba(255,255,255,0.75)' }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLElement
              el.style.background = 'rgba(255,255,255,0.15)'
              el.style.color = '#fff'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLElement
              el.style.background = 'transparent'
              el.style.color = 'rgba(255,255,255,0.75)'
            }}
          >
            <X size={15} />
          </button>
        </div>

        {pageContext && (
          <div
            className="px-4 py-1.5 flex items-center gap-2"
            style={{
              background: 'rgba(0,73,119,0.05)',
              borderBottom: '1px solid var(--border-subtle)',
            }}
          >
            <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--accent)' }} />
            <span className="text-[10px] font-mono truncate" style={{ color: 'var(--accent)' }}>
              {pageContext.slice(0, 80)}
              {pageContext.length > 80 ? '…' : ''}
            </span>
          </div>
        )}

        <div
          className="flex gap-1.5 px-4 py-2.5 flex-wrap"
          style={{ borderBottom: '1px solid var(--border-subtle)' }}
        >
          {QUICK_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => sendMessage(q)}
              className="text-xs px-2.5 py-1 rounded-lg transition-colors font-medium"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                color: 'var(--text-secondary)',
              }}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLElement
                el.style.borderColor = 'var(--accent)'
                el.style.color = 'var(--accent)'
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLElement
                el.style.borderColor = 'var(--border)'
                el.style.color = 'var(--text-secondary)'
              }}
            >
              {q}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-3">
            {messages.length === 0 && (
              <div className="text-center mt-12">
                <div className="text-4xl mb-3 opacity-20">✦</div>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  Ask me to brief, explain, or run a scenario.
                </p>
              </div>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn('flex animate-fade-in', msg.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                <div
                  className="max-w-[88%] rounded-xl px-3 py-2 text-sm"
                  style={
                    msg.role === 'user'
                      ? {
                          background: 'var(--accent-light)',
                          color: 'var(--text-primary)',
                          border: '1px solid var(--accent-light)',
                        }
                      : {
                          background: 'var(--bg-elevated)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }
                  }
                >
                  {msg.role === 'assistant' ? (
                    <div
                      className="max-w-none"
                      style={{
                        fontSize: 12,
                        lineHeight: 1.6,
                        fontFamily: "'Instrument Sans', -apple-system, sans-serif",
                        color: 'var(--text-secondary)',
                      }}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <span style={{ fontSize: 13 }}>{msg.content}</span>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div
                  className="rounded-xl px-3 py-2 text-xs font-mono"
                  style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-muted)',
                  }}
                >
                  <span className="animate-pulse">●●●</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="px-4 py-4" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about a metric, request a scenario, draft a memo…"
              disabled={isLoading}
              className="flex-1 text-sm rounded-xl px-3 py-2.5 transition-all"
              style={{
                background: 'var(--bg-elevated)',
                border: '1.5px solid var(--border)',
                color: 'var(--text-primary)',
              }}
              onFocus={(e) => {
                e.currentTarget.style.background = 'var(--bg-card)'
                e.currentTarget.style.borderColor = 'var(--accent)'
              }}
              onBlur={(e) => {
                e.currentTarget.style.background = 'var(--bg-elevated)'
                e.currentTarget.style.borderColor = 'var(--border)'
              }}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={isLoading || !input.trim()}
              className="px-3 py-2 rounded-xl transition-all disabled:opacity-40"
              style={{ background: 'var(--accent)', color: '#fff' }}
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
