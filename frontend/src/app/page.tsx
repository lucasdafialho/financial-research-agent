'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { BarChart3, FileText, Settings, Trash2 } from 'lucide-react';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatMessages } from '@/components/chat/ChatMessages';
import { StockCard } from '@/components/market/StockCard';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { useChatStore } from '@/store/chat';
import { researchApi, marketApi, healthApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { QueryResponse } from '@/types';

const POPULAR_TICKERS = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 'WEGE3'];

export default function Home() {
  const [activeTab, setActiveTab] = useState<'chat' | 'market' | 'documents'>(
    'chat'
  );
  const {
    messages,
    isLoading,
    addUserMessage,
    addAssistantMessage,
    setLoading,
    clearMessages,
  } = useChatStore();

  const { data: healthStatus } = useQuery({
    queryKey: ['health'],
    queryFn: healthApi.check,
    refetchInterval: 30000,
  });

  const { data: marketData, isLoading: isLoadingMarket } = useQuery({
    queryKey: ['market', POPULAR_TICKERS],
    queryFn: () => marketApi.getQuotes(POPULAR_TICKERS),
    refetchInterval: 60000,
    enabled: activeTab === 'market',
  });

  const queryMutation = useMutation({
    mutationFn: (query: string) => researchApi.submitQuery({ query }),
    onSuccess: (response: QueryResponse) => {
      addAssistantMessage(response.content, response);
      setLoading(false);
    },
    onError: (error: Error) => {
      addAssistantMessage(
        `Desculpe, ocorreu um erro ao processar sua pergunta: ${error.message}`
      );
      setLoading(false);
    },
  });

  const handleSubmit = (message: string) => {
    addUserMessage(message);
    setLoading(true);
    queryMutation.mutate(message);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-50 bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary-600 flex items-center justify-center">
                <BarChart3 className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-gray-900">Financial Research</h1>
                <p className="text-xs text-gray-500">Powered by AI Agents</p>
              </div>
            </div>

            <nav className="flex items-center gap-1">
              {[
                { id: 'chat', label: 'Chat', icon: BarChart3 },
                { id: 'market', label: 'Mercado', icon: BarChart3 },
                { id: 'documents', label: 'Documentos', icon: FileText },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    activeTab === tab.id
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
            </nav>

            <div className="flex items-center gap-3">
              {healthStatus && (
                <div className="flex items-center gap-2 text-sm">
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full',
                      healthStatus.status === 'healthy'
                        ? 'bg-green-500'
                        : 'bg-yellow-500'
                    )}
                  />
                  <span className="text-gray-600">
                    {healthStatus.status === 'healthy' ? 'Online' : 'Degradado'}
                  </span>
                </div>
              )}
              <Button variant="ghost" size="sm">
                <Settings className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'chat' && (
          <div className="flex flex-col h-[calc(100vh-180px)]">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Assistente de Pesquisa
              </h2>
              {messages.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearMessages}
                  className="text-gray-500"
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Limpar
                </Button>
              )}
            </div>

            <Card className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-y-auto scrollbar-thin">
                <ChatMessages messages={messages} />
              </div>
              <div className="border-t border-gray-200 p-4">
                <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'market' && (
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Mercado em Tempo Real
            </h2>

            {isLoadingMarket ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {POPULAR_TICKERS.map((ticker) => (
                  <Card key={ticker} className="animate-pulse">
                    <CardContent className="p-4">
                      <div className="h-6 bg-gray-200 rounded w-20 mb-2" />
                      <div className="h-4 bg-gray-200 rounded w-32 mb-4" />
                      <div className="h-8 bg-gray-200 rounded w-28 mb-4" />
                      <div className="grid grid-cols-2 gap-2">
                        <div className="h-10 bg-gray-200 rounded" />
                        <div className="h-10 bg-gray-200 rounded" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : marketData ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {marketData.map((stock) => (
                  <StockCard
                    key={stock.ticker}
                    data={stock}
                    onClick={() => {
                      setActiveTab('chat');
                      handleSubmit(`Análise completa de ${stock.ticker}`);
                    }}
                  />
                ))}
              </div>
            ) : (
              <p className="text-gray-500">Nenhum dado disponível</p>
            )}
          </div>
        )}

        {activeTab === 'documents' && (
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Documentos
            </h2>
            <Card>
              <CardHeader>
                <CardTitle>Upload de Documentos</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                  <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600 mb-2">
                    Arraste arquivos PDF aqui ou clique para selecionar
                  </p>
                  <p className="text-sm text-gray-500">
                    Balanços, relatórios trimestrais, fatos relevantes
                  </p>
                  <input
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    id="file-upload"
                  />
                  <Button variant="outline" className="mt-4">
                    <label htmlFor="file-upload" className="cursor-pointer">
                      Selecionar Arquivo
                    </label>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
