import { useState, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import ChatPanel from '../chat/ChatPanel'
import { useChatStore } from '@/store/chatStore'

export default function AppShell() {
  const location = useLocation()
  const isOpen = useChatStore((s) => s.isOpen)
  const setOpen = useChatStore((s) => s.setOpen)
  const setFunctionId = useChatStore((s) => s.setFunctionId)
  const [chatVisible, setChatVisible] = useState(false)

  useEffect(() => {
    setChatVisible(isOpen)
  }, [isOpen])

  // Track function context from URL so chat can specialize
  useEffect(() => {
    const m = location.pathname.match(/\/workspace\/([^/]+)/)
    setFunctionId(m ? m[1] : null)
  }, [location.pathname, setFunctionId])

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: 'var(--bg-page)', color: 'var(--text-primary)' }}
    >
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Topbar />
        <main
          className="flex-1 overflow-y-auto"
          style={{ padding: '24px 28px', background: 'var(--bg-page)' }}
        >
          <Outlet />
        </main>
      </div>
      <ChatPanel open={chatVisible} onClose={() => setOpen(false)} />
      {!chatVisible && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full flex items-center justify-center z-50 transition-all hover:scale-105 font-display"
          style={{
            background: 'var(--accent)',
            color: '#FFFFFF',
            fontSize: '20px',
            boxShadow: '0 8px 24px rgba(0,73,119,0.3)',
          }}
          title="Open AI Agent"
        >
          ✦
        </button>
      )}
    </div>
  )
}
