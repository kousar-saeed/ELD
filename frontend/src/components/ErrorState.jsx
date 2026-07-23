import React from 'react';

export default function ErrorState({ error, onRetry }) {
  return (
    <div className="error-state">
      <p>{error || "An error occurred while generating trip plan."}</p>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}
