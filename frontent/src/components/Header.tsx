import React from 'react';
import { Activity, RefreshCw } from 'lucide-react';

interface HeaderProps {
  onRefresh: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onRefresh, isLoading }) => {
  return (
    <header className="bg-gray-900/80 backdrop-blur-md border-b border-gray-700/50 sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Activity className="text-emerald-400" size={24} />
            </div>
            <div>
              <h1 className="text-white text-xl font-bold">Trading Bot</h1>
              <p className="text-gray-400 text-sm">Live Signals Dashboard</p>
            </div>
          </div>
          
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`text-emerald-400 ${isLoading ? 'animate-spin' : ''}`} size={16} />
            <span className="text-emerald-400 font-medium">Refresh</span>
          </button>
        </div>
      </div>
    </header>
  );
};