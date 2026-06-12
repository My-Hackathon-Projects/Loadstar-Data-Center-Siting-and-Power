.PHONY: setup dev web-dev lint format typecheck test pipeline-subset

setup:
	python3 -m pip install -r requirements.txt
	npm --prefix web install

dev:
	python3 -m uvicorn api.app.main:app --reload

web-dev:
	npm --prefix web run dev

lint:
	python3 -m ruff check api engine pipeline db tests
	npm --prefix web run lint

format:
	python3 -m ruff format api engine pipeline db tests
	npm --prefix web run format

typecheck:
	python3 -m pyright api engine
	npm --prefix web run typecheck

test:
	python3 -m pytest
	npm --prefix web run test

pipeline-subset:
	python3 -m pipeline.access_check --write public/docs/access_decisions.md
