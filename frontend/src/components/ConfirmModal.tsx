import { useEffect } from 'react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
  onCancel: () => void;
}

// Warning icon
function WarningIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}

// Trash icon
function TrashIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

// Info icon
function InfoIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onCancel();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const getVariantStyles = () => {
    switch (variant) {
      case 'danger':
        return {
          iconBg: 'bg-red-500/20',
          iconColor: 'text-red-400',
          buttonBg: 'bg-red-600 hover:bg-red-500',
          icon: <TrashIcon />,
        };
      case 'warning':
        return {
          iconBg: 'bg-amber-500/20',
          iconColor: 'text-amber-400',
          buttonBg: 'bg-amber-600 hover:bg-amber-500',
          icon: <WarningIcon />,
        };
      case 'info':
        return {
          iconBg: 'bg-violet-500/20',
          iconColor: 'text-violet-400',
          buttonBg: 'bg-violet-600 hover:bg-violet-500',
          icon: <InfoIcon />,
        };
    }
  };

  const styles = getVariantStyles();

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onCancel}
      />
      
      {/* Modal */}
      <div className="relative bg-slate-800 rounded-2xl shadow-2xl w-full max-w-sm mx-4 border border-violet-500/20 overflow-hidden animate-fade-in">
        {/* Content */}
        <div className="px-6 py-6">
          <div className="flex flex-col items-center text-center">
            {/* Icon */}
            <div className={`w-14 h-14 rounded-full ${styles.iconBg} ${styles.iconColor} flex items-center justify-center mb-4`}>
              {styles.icon}
            </div>
            
            {/* Title */}
            <h3 className="text-lg font-semibold text-white mb-2">
              {title}
            </h3>
            
            {/* Message */}
            <p className="text-sm text-slate-400">
              {message}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 px-6 py-4 bg-slate-900/50 border-t border-violet-500/20">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 text-sm font-medium text-slate-300 hover:text-white bg-slate-700/50 hover:bg-slate-700 rounded-xl transition-colors cursor-pointer"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`flex-1 px-4 py-2.5 text-sm font-medium text-white ${styles.buttonBg} rounded-xl transition-colors cursor-pointer`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
