export interface SeriesInfo {
  store_id: string;
  item_id: string;
}

export interface HistoryPoint {
  date: string; // YYYY-MM-DD
  sales: number;
}

export interface ForecastPoint {
  date: string; // YYYY-MM-DD
  predicted_sales: number;
}
