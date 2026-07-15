import type {
  AccuracyDailyPoint,
  ForecastPoint,
  HistoryPoint,
  SeriesAccuracyPoint,
  SeriesInfo,
} from "./types";

// The serving API from src/retail_demand/serving/app.py. Defaults to a
// locally-running instance since nothing is deployed to GCP yet - see
// frontend/README.md and set NEXT_PUBLIC_API_BASE_URL once it is.
export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchSeries(): Promise<SeriesInfo[]> {
  return fetchJson<SeriesInfo[]>("/series");
}

export function fetchHistory(
  storeId: string,
  itemId: string,
  days = 90,
): Promise<HistoryPoint[]> {
  const params = new URLSearchParams({ days: String(days) });
  return fetchJson<HistoryPoint[]>(
    `/history/${encodeURIComponent(storeId)}/${encodeURIComponent(itemId)}?${params}`,
  );
}

export function fetchForecast(storeId: string, itemId: string): Promise<ForecastPoint> {
  return fetchJson<ForecastPoint>(
    `/forecast/${encodeURIComponent(storeId)}/${encodeURIComponent(itemId)}`,
  );
}

export function fetchAccuracyDaily(): Promise<AccuracyDailyPoint[]> {
  return fetchJson<AccuracyDailyPoint[]>("/accuracy");
}

export function fetchSeriesAccuracy(
  storeId: string,
  itemId: string,
): Promise<SeriesAccuracyPoint[]> {
  return fetchJson<SeriesAccuracyPoint[]>(
    `/accuracy/${encodeURIComponent(storeId)}/${encodeURIComponent(itemId)}`,
  );
}
