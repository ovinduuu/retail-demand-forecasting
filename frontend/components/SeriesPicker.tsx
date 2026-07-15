"use client";

import { useMemo } from "react";
import type { SeriesInfo } from "@/lib/types";
import { formatSeriesLabel } from "@/lib/labels";

interface Props {
  series: SeriesInfo[];
  selected: SeriesInfo | null;
  onSelect: (series: SeriesInfo) => void;
}

function seriesKey(s: SeriesInfo): string {
  return `${s.store_id}::${s.item_id}`;
}

export default function SeriesPicker({ series, selected, onSelect }: Props) {
  // M5's item/store codes have no real product names (see lib/labels.ts) -
  // sorted by the formatted label so the picker groups by state/category
  // instead of raw code order.
  const sorted = useMemo(
    () =>
      [...series].sort((a, b) =>
        formatSeriesLabel(a.store_id, a.item_id).localeCompare(
          formatSeriesLabel(b.store_id, b.item_id),
        ),
      ),
    [series],
  );

  return (
    <div className="flex items-center gap-3">
      <label htmlFor="series-picker" className="text-sm font-medium text-[var(--text-secondary)]">
        Store / item
      </label>
      <select
        id="series-picker"
        className="rounded-md border border-[var(--baseline)] bg-[var(--surface-1)] px-3 py-2 text-sm text-[var(--text-primary)]"
        value={selected ? seriesKey(selected) : ""}
        onChange={(event) => {
          const found = series.find((s) => seriesKey(s) === event.target.value);
          if (found) onSelect(found);
        }}
      >
        {sorted.map((s) => (
          <option key={seriesKey(s)} value={seriesKey(s)}>
            {formatSeriesLabel(s.store_id, s.item_id)}
          </option>
        ))}
      </select>
    </div>
  );
}
