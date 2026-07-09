.PHONY: setup lint test synth-data fmt

setup:
	uv sync --all-extras

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

test:
	uv run pytest -v

synth-data:
	uv run python -m retail_demand.data_engineering.synthetic_daily_feed
