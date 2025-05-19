startd:
	docker-compose --profile tracing up -d --build \
		&& docker-compose run --rm fast-api-docker-poetry poetry run alembic upgrade head

stopd:
	docker-compose down

startslimd:
	docker-compose --profile default up -d --build \
		&& docker-compose run --rm fast-api-docker-poetry poetry run alembic upgrade head

testd:
	docker-compose up -d --build \
		&& docker-compose run --rm fast-api-docker-poetry poetry run pytest -v --durations=10 --durations-min=0.5

startp:
	docker-compose up fast-api-postgres -d \
	&& poetry run alembic upgrade head \
	&& poetry run python -m app.main

testp:
	docker-compose up fast-api-postgres -d \
	&& poetry run pytest -v --durations=10 --durations-min=0.5

create-migration:
	@read -p "Enter rev id: " message; \
	poetry run alembic revision --autogenerate --rev-id "$$message"

create-admin-user:
	docker-compose run --rm fast-api-docker-poetry python create_admin.py