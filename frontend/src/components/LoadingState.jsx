import React from 'react';

export default function LoadingState({ message = "Calculating compliant route & HOS logs..." }) {
  return (
    <div className="loading-state">
      <p>{message}</p>
    </div>
  );
}
