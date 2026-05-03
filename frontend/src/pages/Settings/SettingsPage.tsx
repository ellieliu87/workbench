import { useNavigate, useParams } from 'react-router-dom'
import { BookOpen, Wrench, Code2, Server } from 'lucide-react'
import KnowledgeBaseTab from './KnowledgeBaseTab'
import SkillsTab from './SkillsTab'
import ToolsTab from './ToolsTab'
import McpServersTab from './McpServersTab'

const TABS = [
  { id: 'knowledge',   label: 'Knowledge Base', icon: BookOpen },
  { id: 'skills',      label: 'Agent Skills',   icon: Wrench },
  { id: 'tools',       label: 'Agent Tools',    icon: Code2 },
  { id: 'mcp',         label: 'MCP Servers',    icon: Server },
] as const

export default function SettingsPage() {
  const { tab } = useParams<{ tab?: string }>()
  const navigate = useNavigate()
  // 'datasources' is the legacy route id — keep redirecting it to knowledge
  // base so any saved bookmarks / chat-shared links keep working.
  const rawTab = tab === 'datasources' ? 'knowledge' : (tab as (typeof TABS)[number]['id'] | undefined)
  const active = rawTab || 'knowledge'

  return (
    <div className="max-w-[1320px] mx-auto animate-fade-in">
      <div className="mb-6">
        <h1 className="page-header">Settings</h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Upload reference documents the agents can search, manage agent skills,
          register Python tools, and connect MCP servers.
        </p>
      </div>

      <div
        className="flex items-center gap-1 mb-6"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              onClick={() => navigate(`/settings/${id}`)}
              className="px-4 py-2.5 text-sm font-medium flex items-center gap-2 transition-colors"
              style={{
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                borderBottom: `2px solid ${isActive ? 'var(--accent)' : 'transparent'}`,
                marginBottom: -1,
                fontWeight: isActive ? 600 : 500,
              }}
            >
              <Icon size={14} />
              {label}
            </button>
          )
        })}
      </div>

      {active === 'knowledge' && <KnowledgeBaseTab />}
      {active === 'skills' && <SkillsTab />}
      {active === 'tools' && <ToolsTab />}
      {active === 'mcp' && <McpServersTab />}
    </div>
  )
}
