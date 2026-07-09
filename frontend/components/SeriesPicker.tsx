"use client";

import type { SeriesInfo } from "@/lib/types";

interface Props {
  series: SeriesInfo[];
  selected: SeriesInfo | null;
  onSelect: (series: SeriesInfo) => void;
}

function seriesKey(s: SeriesInfo): string {
  return `${s.store_id}::${s.item_id}`;
}

export default function SeriesPicker({ series, selected, onSelect }: Props) {
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
        {series.map((s) => (
          <option key={seriesKey(s)} value={seriesKey(s)}>
            {s.store_id} / {s.item_id}
          </option>
        ))}
      </select>
    </div>
  );
}
