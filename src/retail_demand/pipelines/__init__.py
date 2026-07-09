"""Vertex AI Pipeline (KFP SDK v2) definitions.

Roadmap Phase 4: a pipeline wiring dbt transform -> feature build -> train ->
evaluate -> conditionally register the model in Vertex AI Model Registry.
Also used to orchestrate the data engineering transform step, so the project
does not need a separately-paid orchestrator (e.g. Cloud Composer).

Planned modules: training_pipeline.py, components/
"""
