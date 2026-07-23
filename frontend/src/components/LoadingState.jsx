import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingState({ message = "Calculating HOS-compliant route & drawing log grids..." }) {
  return (
    <div className="loading-overlay">
      <div className="loading-card">
        <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
        <h4>Processing Trip Plan</h4>
        <p>{message}</p>
        <div className="loading-progress-bar">
          <div className="bar-fill animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}
