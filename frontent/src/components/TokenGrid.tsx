import React from 'react';
import { Token } from '../types/trading';
import { TokenCard } from './TokenCard';

interface TokenGridProps {
  tokens: Token[];
  selectedToken: string | null;
  onSelectToken: (tokenId: string) => void;
  getTokenSignals: (tokenId: string) => any[];
}

export const TokenGrid: React.FC<TokenGridProps> = ({
  tokens,
  selectedToken,
  onSelectToken,
  getTokenSignals
}) => {
  return (
    <div className="mb-8">
      <h2 className="text-white text-2xl font-bold mb-6">Popular Tokens</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {tokens.map(token => (
          <TokenCard
            key={token.id}
            token={token}
            isSelected={selectedToken === token.id}
            onSelect={onSelectToken}
            hasSignals={getTokenSignals(token.id).length > 0}
          />
        ))}
      </div>
    </div>
  );
};