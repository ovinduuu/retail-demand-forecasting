"""Model serving.

Phase 6 (done): batch_predict.py is the primary path - a scheduled,
one-step-ahead scoring script against BigQuery's fct_sales mart (Cloud
Scheduler -> Cloud Run Job, see infra/terraform), cheaper than a standing
Vertex AI endpoint. app.py is a FastAPI service implementing Vertex's
predict/health contract, used for the optional Cloud Run live-request demo
and as the serving_container_image_uri Phase 4's register_model needs.

Not yet deployed anywhere real - needs infra/terraform applied and the
serving image (../../../docker/serving.Dockerfile) built and pushed.
"""
