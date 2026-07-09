"""Vertex AI Pipeline (KFP SDK v2) definitions.

Phase 4 (done): components.py (dbt transform, extract training data, train,
register) and training_pipeline.py (wires them with a conditional
registration gate). Compiles locally to a pipeline spec (see
tests/test_training_pipeline.py) but has not been submitted to a real
Vertex AI Pipelines run — that needs infra/terraform applied, the pipeline
image (../../../Dockerfile) built and pushed, and a serving image from
Phase 6.
"""
