import { AlertCircle, Inbox } from "lucide-react";
import { Button } from "./Button";

export function LoadingState({ label = "Loading local usage data" }: { label?: string }) {
  return <div className="query-state loading-state" role="status"><span className="loader" />{label}</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="query-state error-state" role="alert">
      <AlertCircle aria-hidden="true" size={22} />
      <div><strong>Data unavailable</strong><p>{message}</p></div>
      {onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="query-state empty-state">
      <Inbox aria-hidden="true" size={24} />
      <div><strong>{title}</strong><p>{message}</p></div>
    </div>
  );
}
