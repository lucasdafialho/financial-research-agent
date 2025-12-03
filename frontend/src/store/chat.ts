import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, QueryResponse } from '@/types';
import { generateId } from '@/lib/utils';

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  addUserMessage: (content: string) => string;
  addAssistantMessage: (content: string, response?: QueryResponse) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      isLoading: false,
      error: null,

      addUserMessage: (content: string) => {
        const id = generateId();
        set((state) => ({
          messages: [
            ...state.messages,
            {
              id,
              role: 'user',
              content,
              timestamp: new Date(),
            },
          ],
        }));
        return id;
      },

      addAssistantMessage: (content: string, response?: QueryResponse) => {
        set((state) => ({
          messages: [
            ...state.messages,
            {
              id: generateId(),
              role: 'assistant',
              content,
              timestamp: new Date(),
              response,
            },
          ],
        }));
      },

      updateMessage: (id: string, updates: Partial<ChatMessage>) => {
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id ? { ...msg, ...updates } : msg
          ),
        }));
      },

      setLoading: (loading: boolean) => set({ isLoading: loading }),

      setError: (error: string | null) => set({ error }),

      clearMessages: () => set({ messages: [], error: null }),
    }),
    {
      name: 'chat-storage',
      partialize: (state) => ({ messages: state.messages }),
    }
  )
);
