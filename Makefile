TEST_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.test.yml

.PHONY: test
test:
	docker compose down && \
	$(TEST_COMPOSE) up --build --abort-on-container-exit --attach test || \
	$(TEST_COMPOSE) down -v

.PHONY: dev
dev:
	docker compose down && \
	docker compose up -d --force-recreate --build