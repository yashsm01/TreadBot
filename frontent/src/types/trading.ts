export interface Token {
  id: string;
  symbol: string;
  name: string;
  price: number;
  change24h: number;
  volume: number;
  marketCap: number;
  icon: string;
}

export interface TradingSignal {
  id: string;
  tokenId: string;
  type: 'LONG' | 'SHORT';
  entry: number;
  stopLoss: number;
  takeProfit: number;
  confidence: number;
  timestamp: Date;
  status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  pnl?: number;
}

export interface MarketData {
  tokens: Token[];
  signals: TradingSignal[];
  selectedToken: string | null;
}