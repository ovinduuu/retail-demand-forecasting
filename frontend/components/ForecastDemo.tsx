"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { fetchForecast, fetchHistory, getApiBaseUrl } from "@/lib/api";
import type { ForecastPoint, HistoryPoint, SeriesInfo } from "@/lib/types";
import SeriesPicker from "./SeriesPicker";
import ForecastChart from "./ForecastChart";

interface Props {
  initialSeries: SeriesInfo[];
  initialError: string | null;
}

export default function ForecastDemo({ initialSeries, initialError }: Props) {
  const [selected, setSelected] = useState<SeriesInfo | null>(initialSeries[0] ?? null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint | null>(null);
  const [error, setError] = useState<string | null>(initialError);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;

    startTransition(async () => {
      try {
        const [historyData, forecastData] = await Promise.all([
          fetchHistory(selected.store_id, selected.item_id, 90),
          fetchForecast(selected.store_id, selected.item_id),
        ]);
        if (cancelled) return;
        setHistory(historyData);
        setForecast(forecastData);
        setError(null);
      } catch (err: unknown) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load data");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [selected]);

  const seriesLabel = useMemo(
    () => (selected ? `${selected.store_id} / ${selected.item_id}` : ""),
    [selected],
  );

  if (initialSeries.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--baseline)] p-8 text-sm">
        <p className="font-medium text-[var(--text-primary)]">Backend not reachable.</p>
        <p className="mt-2 text-[var(--text-secondary)]">
          {initialError ?? "No series returned."} Trying to reach{" "}
          <code className="rounded bg-[var(--surface-1)] px-1 py-0.5">{getApiBaseUrl()}</code>.
          Set <code className="rounded bg-[var(--surface-1)] px-1 py-0.5">
            NEXT_PUBLIC_API_BASE_URL
          </code>{" "}
          to a running instance of the serving API — see{" "}
          <code className="rounded bg-[var(--surface-1)] px-1 py-0.5">frontend/README.md</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <SeriesPicker series={initialSeries} selected={selected} onSelect={setSelected} />
      {error && <p className="text-sm text-[var(--status-critical)]">{error}</p>}
      <ForecastChart
        history={history}
        forecast={forecast}
        seriesLabel={seriesLabel}
        loading={isPending}
      />
    </div>
  );
}
