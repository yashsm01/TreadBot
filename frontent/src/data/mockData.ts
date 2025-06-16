import { Token, TradingSignal } from '../types/trading';

export const mockTokens: Token[] = [
  {
    id: 'bitcoin',
    symbol: 'BTC',
    name: 'Bitcoin',
    price: 43250.45,
    change24h: 2.34,
    volume: 28500000000,
    marketCap: 847000000000,
    icon: '₿'
  },
  {
    id: 'ethereum',
    symbol: 'ETH',
    name: 'Ethereum',
    price: 2645.78,
    change24h: -1.23,
    volume: 15200000000,
    marketCap: 318000000000,
    icon: 'Ξ'
  },
  {
    id: 'solana',
    symbol: 'SOL',
    name: 'Solana',
    price: 98.45,
    change24h: 5.67,
    volume: 2800000000,
    marketCap: 42000000000,
    icon: '◎'
  },
  {
    id: 'cardano',
    symbol: 'ADA',
    name: 'Cardano',
    price: 0.485,
    change24h: -2.15,
    volume: 450000000,
    marketCap: 17000000000,
    icon: '₳'
  },
  {
    id: 'polkadot',
    symbol: 'DOT',
    name: 'Polkadot',
    price: 7.23,
    change24h: 3.45,
    volume: 320000000,
    marketCap: 9200000000,
    icon: '●'
  },
  {
    id: 'chainlink',
    symbol: 'LINK',
    name: 'Chainlink',
    price: 14.67,
    change24h: 1.89,
    volume: 580000000,
    marketCap: 8600000000,
    icon: '🔗'
  },
  {
    id: 'polygon',
    symbol: 'MATIC',
    name: 'Polygon',
    price: 0.842,
    change24h: -0.76,
    volume: 385000000,
    marketCap: 7800000000,
    icon: '▲'
  },
  {
    id: 'avalanche',
    symbol: 'AVAX',
    name: 'Avalanche',
    price: 36.78,
    change24h: 4.23,
    volume: 520000000,
    marketCap: 13500000000,
    icon: '🔺'
  }
];

export const mockSignals: TradingSignal[] = [
  {
    id: 'signal-1',
    tokenId: 'bitcoin',
    type: 'LONG',
    entry: 43200,
    stopLoss: 42500,
    takeProfit: 44800,
    confidence: 78,
    timestamp: new Date(Date.now() - 1000 * 60 * 15),
    status: 'ACTIVE'
  },
  {
    id: 'signal-2',
    tokenId: 'ethereum',
    type: 'SHORT',
    entry: 2650,
    stopLoss: 2720,
    takeProfit: 2520,
    confidence: 65,
    timestamp: new Date(Date.now() - 1000 * 60 * 45),
    status: 'ACTIVE'
  },
  {
    id: 'signal-3',
    tokenId: 'solana',
    type: 'LONG',
    entry: 97.50,
    stopLoss: 94.00,
    takeProfit: 105.00,
    confidence: 82,
    timestamp: new Date(Date.now() - 1000 * 60 * 30),
    status: 'ACTIVE'
  }
];