export interface Token {
  id: string;
  symbol: string;
  name: string;
  price: number;
  change24h: number;
  volume: number;
  marketCap: number;
  icon: string;
  high24h?: number;
  low24h?: number;
  volatility?: number;
  timestamp?: number;
}

export interface TradingSignal {
  id: string;
  tokenId: string;
  type: "LONG" | "SHORT";
  entry: number;
  stopLoss: number;
  takeProfit: number;
  confidence: number;
  timestamp: Date;
  status: "ACTIVE" | "COMPLETED" | "CANCELLED";
  pnl?: number;
  momentum?: number;
  volatility?: number;
}

export interface MarketData {
  tokens: Token[];
  signals: TradingSignal[];
  selectedToken: string | null;
}

export interface MarketSummary {
  totalTokens: number;
  totalVolume: number;
  averageChange24h: number;
  positivePerformers: number;
  negativePerformers: number;
  activeSignals: number;
  timestamp: number;
}
