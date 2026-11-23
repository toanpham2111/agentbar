import type { AdapterStatus } from "../../types/usage";

const labels: Record<AdapterStatus, string> = {
  available: "Connected",
  partially_supported: "Partial support",
  not_installed: "Not installed",
  authentication_required: "Authentication required",
  permission_required: "Permission required",
  unsupported: "Usage unsupported",
  error: "Collection error",
};

export function StatusBadge({ status }: { status: AdapterStatus }) {
  return <span className={`status-badge status-${status}`}>{labels[status]}</span>;
}
