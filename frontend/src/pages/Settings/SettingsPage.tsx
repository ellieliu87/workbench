import { useNavigate, useParams } from 'react-router-dom'
import { Database, Wrench, Code2 } from 'lucide-react'
import DataSourcesTab from './DataSourcesTab'
import SkillsTab from './SkillsTab'
import ToolsTab from './ToolsTab'

const TABS = [
  { id: 'datasources', label: 'Data Sources', icon: Database },
  { id: 'skills',      label: 'Agent Skills', icon: Wrench },
  { id: 'tools',       label: 'Python Tools', icon: Code2 },
] as const

export default function SettingsPage() {
  const { tab } = useParams<{ tab?: string }>()
  const navigate = useNavigate()
  const active = (tab as (typeof TABS)[number]['id']) || 'datasources'

  return (
    <div className="max-w-[1320px] mx-auto animate-fade-in">
      <div className="mb-6">
        <h1 className="page-header">Settings</h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Configure the data sources your workspaces and agent will use, manage agent skills,
          and design custom plots that can be added to any workspace.
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

      {active === 'datasources' && <DataSourcesTab />}
      {active === 'skills' && <SkillsTab />}
      {active === 'tools' && <ToolsTab />}
    </div>
  )
}
