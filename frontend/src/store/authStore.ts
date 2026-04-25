import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  username: string | null
  role: string | null
  department: string | null
  setAuth: (a: { token: string; username: string; role: string; department: string }) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      role: null,
      department: null,
      setAuth: (a) => set(a),
      logout: () => set({ token: null, username: null, role: null, department: null }),
    }),
    { name: 'cma-auth' },
  ),
)
