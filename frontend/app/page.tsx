import { fetchSeries } from "@/lib/api";
import type { SeriesInfo } from "@/lib/types";
import ForecastDemo from "@/components/ForecastDemo";

export default async function Home() {
  let series: SeriesInfo[] = [];
  let loadError: string | null = null;
  try {
    series = await fetchSeries();
  } catch (err: unknown) {
    loadError = err instanceof Error ? err.message : "Unknown error";
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-12">
      <header>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
          Retail demand forecast
        </h1>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Pick a store/item to see recent sales and the model&apos;s one-step-ahead forecast.
        </p>
      </header>
      <ForecastDemo initialSeries={series} initialError={loadError} />
    </main>
  );
}
