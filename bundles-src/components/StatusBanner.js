import React from 'react';

const StatusBanner = ({ kind = 'success', text, action, onClose }) => (
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
    {action && (
      <>
        {' '}
        <a className="alert-link" href={action.href}>
          {action.label}
        </a>
      </>
    )}
  </div>
);

export default StatusBanner;
