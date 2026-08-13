'use client';

import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react';
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { cn } from '@hietedu/ui';

import { useI18n } from '@/lib/i18n';

type Tone = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  tone: Tone;
  message: string;
  detail?: string;
}

interface ToastContextValue {
  notify: (message: string, tone?: Tone, detail?: string) => void;
  /** Run an async action, showing a success or the thrown error message. */
  run: <T>(action: () => Promise<T>, successMessage?: string) => Promise<T | undefined>;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

/**
 * Feedback for every admin action.
 *
 * `run` exists because the alternative — a try/catch with two setState calls at each of the ~90
 * call sites — is where "the button silently did nothing" bugs come from. Wrapping the action
 * means an API error always reaches the user as the message the backend actually sent.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, tone: Tone = 'success', detail?: string) => {
      const id = nextId++;
      setToasts((current) => [...current, { id, tone, message, detail }]);
      // Errors stay longer: they usually need reading, and often acting on.
      window.setTimeout(() => dismiss(id), tone === 'error' ? 8000 : 4000);
    },
    [dismiss],
  );

  const run = useCallback(
    async <T,>(action: () => Promise<T>, successMessage?: string) => {
      try {
        const result = await action();
        if (successMessage) notify(successMessage, 'success');
        return result;
      } catch (caught) {
        notify((caught as Error).message || t('admin.a.somethingWrong'), 'error');
        return undefined;
      }
    },
    [notify, t],
  );

  const value = useMemo(() => ({ notify, run }), [notify, run]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((toast) => {
          const Icon =
            toast.tone === 'success' ? CheckCircle2 : toast.tone === 'error' ? AlertTriangle : Info;
          return (
            <div
              key={toast.id}
              role="status"
              className={cn(
                'pointer-events-auto flex items-start gap-3 rounded-2xl border-2 p-4 shadow-pop-sm',
                toast.tone === 'success' && 'border-teal-300 bg-teal-50 text-teal-900',
                toast.tone === 'error' && 'border-coral-300 bg-coral-50 text-coral-900',
                toast.tone === 'info' && 'border-brand-200 bg-brand-50 text-brand-900',
              )}
            >
              <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-bold">{toast.message}</p>
                {toast.detail && <p className="mt-0.5 text-xs opacity-80">{toast.detail}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                aria-label={t('admin.a.dismiss')}
                className="rounded-lg p-1 hover:bg-black/5"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside a ToastProvider');
  return context;
}
