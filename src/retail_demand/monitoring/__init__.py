"""Model and data monitoring.

Phase 7 (done): drift_check.py computes Population Stability Index per
numeric feature between a reference and current window and logs results to
BigQuery - a custom substitute for Vertex AI Model Monitoring, which watches
a live Endpoint's request logs and doesn't apply to this project's
batch-first serving path (see docs/architecture.md). retrain_trigger.py
reads the latest drift + evaluation metrics from BigQuery and submits a new
training pipeline run (reusing pipelines/submit_pipeline.py) if either has
regressed. Both are meant to run as scheduled Cloud Run Jobs (Cloud
Scheduler -> Cloud Run Job, not Cloud Function - keeps everything on one
container-based pattern already used elsewhere in this project).

See docs/monitoring.md for the BigQuery tables involved and how to point a
Looker Studio dashboard at them.
"""
