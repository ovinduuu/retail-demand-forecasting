"""Vertex AI Pipeline (KFP SDK v2) definitions.

Phase 4 (done): components.py (dbt transform, extract training data, train,
register) and training_pipeline.py (wires them with a conditional
registration gate). Compiles locally to a pipeline spec (see
tests/test_training_pipeline.py).

Phase 5 (done): submit_pipeline.py compiles and submits the pipeline as a
Vertex AI Pipeline Job; ../../../cloudbuild.yaml calls it after building and
pushing the pipeline image.

Still not run against a real GCP project — needs infra/terraform applied,
the pipeline image (../../../Dockerfile) built and pushed, and a serving
image from Phase 6.
"""
