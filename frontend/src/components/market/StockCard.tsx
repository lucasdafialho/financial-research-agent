'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import {
  formatCurrency,
  formatPercent,
  formatMarketCap,
  getChangeColor,
  cn,
} from '@/lib/utils';
import type { MarketData } from '@/types';

interface StockCardProps {
  data: MarketData;
  onClick?: () => void;
}

export function StockCard({ data, onClick }: StockCardProps) {
  const changeColor = getChangeColor(data.change_percent);
  const TrendIcon =
    data.change_percent > 0
      ? TrendingUp
      : data.change_percent < 0
      ? TrendingDown
      : Minus;

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all hover:shadow-md hover:border-primary-300',
        onClick && 'hover:scale-[1.02]'
      )}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-bold text-lg text-gray-900">{data.ticker}</h3>
            <p className="text-sm text-gray-600 truncate max-w-[150px]">
              {data.company_name}
            </p>
          </div>
          <div className={cn('flex items-center gap-1', changeColor)}>
            <TrendIcon className="h-4 w-4" />
            <span className="font-medium">{formatPercent(data.change_percent)}</span>
          </div>
        </div>

        <div className="text-2xl font-bold text-gray-900 mb-3">
          {formatCurrency(data.current_price)}
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-gray-500">Volume</span>
            <p className="font-medium text-gray-900">
              {data.volume.toLocaleString('pt-BR')}
            </p>
          </div>
          <div>
            <span className="text-gray-500">Market Cap</span>
            <p className="font-medium text-gray-900">
              {formatMarketCap(data.market_cap)}
            </p>
          </div>
          {data.pe_ratio && (
            <div>
              <span className="text-gray-500">P/E</span>
              <p className="font-medium text-gray-900">
                {data.pe_ratio.toFixed(2)}
              </p>
            </div>
          )}
          {data.dividend_yield && (
            <div>
              <span className="text-gray-500">Div. Yield</span>
              <p className="font-medium text-gray-900">
                {(data.dividend_yield * 100).toFixed(2)}%
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
