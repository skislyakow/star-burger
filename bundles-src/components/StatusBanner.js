import React from 'react';

const StatusBanner = ({ kind = 'success', text, onClose }) => (
  <div className={`alert alert-${kind} status-banner`} role="alert">
    <button
      type="button"
      className="close"
      aria-label="Закрыть"
      onClick={onClose}
    >
      <span aria-hidden="true">×</span>
    </button>
    {text}
  </div>
);

export default StatusBanner;
