export interface ToastItem {
  id: number;
  message: string;
  tone: 'info' | 'error';
}

export function ToastStack({ toasts }: { toasts: ToastItem[] }) {
  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="false">
      {toasts.map((item) => (
        <div className={`toast ${item.tone}`} key={item.id} role="status">
          {item.message}
        </div>
      ))}
    </div>
  );
}
