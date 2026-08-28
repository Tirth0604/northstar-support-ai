.PHONY: install backend frontend migrate seed test lint evaluate docker-up docker-down
install:
	python -m pip install -e "./backend[dev]"
	cd frontend && npm ci
backend:
	cd backend && uvicorn app.main:app --reload
frontend:
	cd frontend && npm run dev
migrate:
	cd backend && alembic upgrade head
seed:
	cd backend && python -m app.seed
test:
	cd backend && pytest
lint:
	cd backend && ruff check app tests && mypy app
	cd frontend && npm run lint
evaluate:
	python evaluation/run_evaluation.py
docker-up:
	docker compose up --build
docker-down:
	docker compose down
