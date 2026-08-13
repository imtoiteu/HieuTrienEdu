'use client';

import { AlertTriangle, X } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { Button, cn } from '@hietedu/ui';

import { useI18n } from '@/lib/i18n';

/**
 * Modal dialog.
 *
 * Focus is moved into the panel on open and Escape closes it, because an admin doing bulk work
 * lives on the keyboard and a modal that traps neither focus nor Escape is worse than no modal.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    // Stop the page behind scrolling under the overlay.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panelRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-ink-900/40 p-4 sm:items-center">
      <button
        type="button"
        aria-label={t('admin.a.close')}
        onClick={onClose}
        className="absolute inset-0 cursor-default"
        tabIndex={-1}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          'relative my-8 w-full rounded-3xl border-2 border-ink-900 bg-white shadow-pop outline-none',
          size === 'sm' && 'max-w-md',
          size === 'md' && 'max-w-xl',
          size === 'lg' && 'max-w-3xl',
          size === 'xl' && 'max-w-5xl',
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b-2 border-ink-100 p-5">
          <div className="min-w-0">
            <h2 className="font-display text-xl">{title}</h2>
            {description && <p className="mt-1 text-sm text-ink-600">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('admin.a.close')}
            className="rounded-xl p-2 text-ink-500 hover:bg-ink-100"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="max-h-[65vh] overflow-y-auto p-5">{children}</div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-2 border-t-2 border-ink-100 p-5">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Destructive-action confirmation.
 *
 * When `confirmText` is given the button stays disabled until the exact text is typed. That is
 * reserved for deletions that cascade — deleting a course also deletes its modules, topics,
 * skills and lessons, and a single mis-click should not be able to do that.
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel,
  confirmText,
  tone = 'danger',
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  confirmText?: string;
  tone?: 'danger' | 'default';
}) {
  const { t } = useI18n();
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setTyped('');
  }, [open]);

  const blocked = Boolean(confirmText) && typed.trim() !== confirmText;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            {t('admin.a.cancel')}
          </Button>
          <Button
            variant={tone === 'danger' ? 'coral' : 'primary'}
            disabled={blocked}
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onConfirm();
                onClose();
              } finally {
                setBusy(false);
              }
            }}
          >
            {confirmLabel ?? t('admin.a.delete')}
          </Button>
        </>
      }
    >
      <div className="flex gap-3">
        {tone === 'danger' && (
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-coral-600" aria-hidden="true" />
        )}
        <div className="min-w-0 text-sm text-ink-700">{message}</div>
      </div>
      {confirmText && (
        <label className="mt-4 block">
          <span className="text-xs font-bold text-ink-700">
            {t('admin.a.typeToConfirm', { text: confirmText })}
          </span>
          <input
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            className="mt-1.5 w-full rounded-xl border-2 border-ink-200 px-3 py-2 text-sm outline-none focus:border-brand-400"
            autoComplete="off"
          />
        </label>
      )}
    </Modal>
  );
}
