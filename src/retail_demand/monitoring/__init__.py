"""Model and data monitoring.

Roadmap Phase 7: Vertex AI Model Monitoring for training/serving skew and
drift, evaluation metrics logged to BigQuery, a retraining trigger (Cloud
Scheduler -> Cloud Function -> Vertex AI Pipeline run), and a lightweight
dashboard over the logged metrics.

Planned modules: drift_check.py, retrain_trigger.py
"""
