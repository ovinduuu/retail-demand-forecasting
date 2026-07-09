"""Model serving.

Phase 6 (done): batch_predict.py is the primary path - a scheduled,
one-step-ahead scoring script against BigQuery's fct_sales mart (Cloud
Scheduler -> Cloud Run Job, see infra/terraform), cheaper than a standing
Vertex AI endpoint. app.py is a FastAPI service implementing Vertex's
predict/health contract, used for the optional Cloud Run live-request demo
and as the serving_container_image_uri Phase 4's register_model needs.

Phase 9: app.py also exposes /series, /history/{store_id}/{item_id}, and
/forecast/{store_id}/{item_id} for the Next.js frontend (../../../frontend)
to call - a small read/forecast API layered on top of the same model and
BigQuery mart, with a LOCAL_DATA_CSV fallback for local development.

Not yet deployed anywhere real - needs infra/terraform applied and the
serving image (../../../docker/serving.Dockerfile) built and pushed.
"""
