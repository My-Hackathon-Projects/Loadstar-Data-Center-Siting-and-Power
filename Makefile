.PHONY: setup dev frontend-dev web-dev frontend-types lint format typecheck test e2e migrate migrate-sqlite pipeline-subset ingest-subset carbon-subset alphaearth-land-subset features-subset siting-model-subset layer-assets

setup:
	python3 -m pip install -r requirements.txt
	npm --prefix frontend install

dev:
	python3 -m uvicorn backend.api.main:app --reload

frontend-dev:
	npm --prefix frontend run dev

web-dev: frontend-dev

frontend-types:
	npm --prefix frontend run generate:types

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

# End-to-end demo-path test. Kept out of `test` because it boots the API and
# Vite dev servers (see frontend/playwright.config.ts) rather than running as a
# fast, serverless unit gate. Regenerates the static layer overlays first so the
# dashboard's static-asset probe resolves and the console stays clean.
e2e:
	python3 -m backend.pipeline.build_layer_assets
	npm --prefix frontend run test:e2e

migrate:
	python3 -m backend.db.migrate

migrate-sqlite:
	python3 -m backend.db.migrate --database data/loadstar.db

pipeline-subset:
	python3 -m backend.pipeline.access_check --write public/docs/access_decisions.md

ingest-subset:
	python3 -m backend.pipeline.subset_ingestion --countries SE,DE,IE --output-dir data/processed/subset --metadata-database data/processed/source_artifacts.db

carbon-subset:
	python3 -m backend.pipeline.hourly_carbon --countries SE,DE,IE --output-dir data/processed/subset --metadata-database data/processed/source_artifacts.db

alphaearth-land-subset:
	python3 -m backend.pipeline.alphaearth_land --countries SE,DE,IE --output-dir data/processed/subset --eval-dir eval --metadata-database data/processed/source_artifacts.db

features-subset:
	python3 -m backend.pipeline.feature_engineering --countries SE,DE,IE --input-dir data/processed/subset --output-dir data/processed/subset --metadata-database data/processed/source_artifacts.db

siting-model-subset:
	python3 -m backend.pipeline.siting_model --countries SE,DE,IE --input-dir data/processed/subset --output-dir data/processed/subset --eval-dir eval --metadata-database data/processed/source_artifacts.db

layer-assets:
	python3 -m backend.pipeline.build_layer_assets
