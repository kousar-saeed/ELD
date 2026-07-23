import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorState({ error, onRetry }) {
  return (
    <div className="error-banner">
      <div className="error-icon">
        <AlertCircle className="w-6 h-6 text-rose-400" />
      </div>
      <div className="error-content">
        <h4>Planning Request Error</h4>
        <p>{error || "Could not generate trip plan. Please check your inputs and try again."}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="retry-btn">
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      )}
    </div>
  );
}
