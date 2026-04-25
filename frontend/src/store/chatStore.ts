import { create } from 'zustand'
import type { ChatMessageItem } from '@/types'

interface ChatState {
  messages: ChatMessageItem[]
  isLoading: boolean
  isOpen: boolean
  pageContext: string | null
  functionId: string | null
  addMessage: (m: Omit<ChatMessageItem, 'id'>) => void
  clearMessages: () => void
  setLoading: (b: boolean) => void
  setOpen: (b: boolean) => void
  setPageContext: (s: string | null) => void
  setFunctionId: (s: string | null) => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  isOpen: false,
  pageContext: null,
  functionId: null,
  addMessage: (m) =>
    set((s) => ({
      messages: [...s.messages, { ...m, id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }],
    })),
  clearMessages: () => set({ messages: [] }),
  setLoading: (b) => set({ isLoading: b }),
  setOpen: (b) => set({ isOpen: b }),
  setPageContext: (s) => set({ pageContext: s }),
  setFunctionId: (s) => set({ functionId: s }),
}))
