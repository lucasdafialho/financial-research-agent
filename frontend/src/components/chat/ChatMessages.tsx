'use client';

import { useEffect, useRef } from 'react';
import { MessageSquare } from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import type { ChatMessage as ChatMessageType } from '@/types';

interface ChatMessagesProps {
  messages: ChatMessageType[];
}

export function ChatMessages({ messages }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mb-4">
          <MessageSquare className="h-8 w-8 text-primary-600" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Assistente de Pesquisa Financeira
        </h2>
        <p className="text-gray-600 max-w-md mb-6">
          Faça perguntas sobre ações brasileiras, análises financeiras, notícias
          de mercado e muito mais. Nossos agentes de IA vão pesquisar e analisar
          as informações para você.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
          {[
            'Qual a situação financeira da Petrobras?',
            'Compare VALE3 e PETR4',
            'Quais as últimas notícias sobre o Itaú?',
            'Análise do setor de varejo brasileiro',
          ].map((suggestion, idx) => (
            <button
              key={idx}
              className="text-left p-3 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors text-sm text-gray-700"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
