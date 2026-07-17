import type { ModelInfo } from "@/lib/types";

interface Props {
  info: ModelInfo | null;
}

function formatTrainedAt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// Retraining otherwise happens entirely server-side (a daily scheduled Cloud
// Run Job) with no visible trace on the site - this makes "the model just
// retrained/improved" a concrete, checkable fact instead of something only
// evident by comparing BigQuery rows.
export default function ModelInfoCard({ info }: Props) {
  if (!info) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-md border border-[var(--gridline)] bg-[var(--surface-1)] px-4 py-3 text-xs text-[var(--text-secondary)]">
      <span>
        <span className="font-medium text-[var(--text-primary)]">Current model</span> · trained{" "}
        {formatTrainedAt(info.trained_at)}
      </span>
      <span>WRMSSE {info.wrmsse.toFixed(4)}</span>
      <span>MAPE {(info.mape * 100).toFixed(1)}%</span>
      <span>RMSE {info.rmse.toFixed(3)}</span>
      <span>{info.n_train_rows.toLocaleString()} training rows</span>
    </div>
  );
}
