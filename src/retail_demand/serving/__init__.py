"""Model serving.

Roadmap Phase 6: primary path is a scheduled Vertex AI batch prediction job
(matches retail replenishment cadence and avoids paying for an always-on
endpoint). A small FastAPI app deployed to Cloud Run is planned as an optional
live-request demo on top of the same model artifact.

Planned modules: batch_predict.py, app.py
"""
