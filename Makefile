.PHONY: setup dev web-dev lint format typecheck test migrate pipeline-subset ingest-subset carbon-subset features-subset

setup:
	python3 -m pip install -r requirements.txt
	npm --prefix frontend install

dev:
	python3 -m uvicorn backend.api.main:app --reload

web-dev:
	npm --prefix frontend run dev

lint:
	python3 -m ruff check backend
	npm --prefix frontend run lint

format:
	python3 -m ruff format backend
	npm --prefix frontend run format

typecheck:
	python3 -m pyright backend/api backend/engine backend/pipeline
	npm --prefix frontend run typecheck

test:
	python3 -m pytest
	npm --prefix frontend run test

migrate:
	python3 -m backend.db.migrate

pipeline-subset:
	python3 -m backend.pipeline.access_check --write public/docs/access_decisions.md

ingest-subset:
	python3 -m backend.pipeline.subset_ingestion --countries SE,DE,IE --output-dir data/processed/subset --metadata-database data/processed/source_artifacts.db

carbon-subset:
	python3 -m backend.pipeline.hourly_carbon --countries SE,DE,IE --output-dir data/processed/subset --metadata-database data/processed/source_artifacts.db

features-subset:
	python3 -m backend.pipeline.feature_engineering --countries SE,DE,IE --input-dir data/processed/subset --output-dir data/processed/subset --metadata-database data/processed/source_artifacts.db
