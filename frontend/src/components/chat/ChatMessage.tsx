'use client';

import { User, Bot, Clock, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import { formatDateTime } from '@/lib/utils';
import type { ChatMessage as ChatMessageType } from '@/types';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex gap-4 p-4 rounded-xl',
        isUser ? 'bg-primary-50' : 'bg-gray-50'
      )}
    >
      <div
        className={cn(
          'flex h-10 w-10 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'
        )}
      >
        {isUser ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="font-medium text-gray-900">
            {isUser ? 'Você' : 'Assistente'}
          </span>
          <span className="flex items-center gap-1 text-xs text-gray-500">
            <Clock className="h-3 w-3" />
            {formatDateTime(message.timestamp)}
          </span>
        </div>

        {message.isLoading ? (
          <div className="flex items-center gap-2 text-gray-500">
            <div className="flex gap-1">
              <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" />
              <span
                className="h-2 w-2 rounded-full bg-gray-400 animate-bounce"
                style={{ animationDelay: '0.1s' }}
              />
              <span
                className="h-2 w-2 rounded-full bg-gray-400 animate-bounce"
                style={{ animationDelay: '0.2s' }}
              />
            </div>
            <span className="text-sm">Analisando sua pergunta...</span>
          </div>
        ) : (
          <div className="markdown-content prose prose-gray max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.response && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            {message.response.sources.length > 0 && (
              <div className="mb-3">
                <h4 className="text-sm font-medium text-gray-700 mb-1">
                  Fontes utilizadas:
                </h4>
                <ul className="text-sm text-gray-600">
                  {message.response.sources.map((source, idx) => (
                    <li key={idx} className="flex items-center gap-1">
                      <span className="text-primary-600">•</span>
                      {source}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {message.response.disclaimers.length > 0 && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 rounded-lg">
                <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-xs text-amber-800">
                  {message.response.disclaimers[0]}
                </div>
              </div>
            )}

            <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
              <span>
                Tempo de processamento:{' '}
                {message.response.processing_time_ms.toFixed(0)}ms
              </span>
              {message.response.analysis?.confidence_score && (
                <span>
                  Confiança:{' '}
                  {(message.response.analysis.confidence_score * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
