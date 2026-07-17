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

export interface AccuracyDailyPoint {
  date: string; // YYYY-MM-DD
  n_predictions: number;
  mae: number;
  mape: number | null; // fraction, e.g. 0.25 = 25% - null if no actual sales were nonzero that day
  rmse: number;
}

export interface SeriesAccuracyPoint {
  date: string; // YYYY-MM-DD
  predicted_sales: number;
  actual_sales: number;
}

export interface ModelInfo {
  trained_at: string; // ISO timestamp
  wrmsse: number;
  mape: number;
  rmse: number;
  n_train_rows: number;
}
