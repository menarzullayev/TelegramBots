.PHONY: dev test lint migrate deploy-stage deploy-prod logs backup

dev:
	docker-compose up --build

test:
	pytest tests/ -v --cov=services --cov-report=html

lint:
	ruff check services/
	mypy services/

migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

deploy-stage:
	docker-compose -f docker-compose.staging.yml up -d --build

deploy-prod:
	docker-compose -f docker-compose.yml up -d --build

logs:
	docker-compose logs -f --tail=100

backup:
	docker exec postgres pg_dump -U tezmath tezmath > backup_$(shell date +%Y%m%d_%H%M%S).sql

restart:
	docker-compose restart

stop:
	docker-compose down

clean:
	docker-compose down -v --remove-orphans
