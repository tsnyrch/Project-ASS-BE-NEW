start:
	docker-compose --profile tracing up -d --build \
		&& docker-compose run --rm fast-api-docker-poetry poetry run alembic upgrade head \
		&& docker-compose run --rm fast-api-docker-poetry python create_admin.py

stop:
	docker-compose down
