TEST_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.test.yml
PROFILE_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.profile.yml

.PHONY: test
test:
	docker compose down -v && \
	$(TEST_COMPOSE) up --build --remove-orphans--abort-on-container-exit --attach test || \
	$(TEST_COMPOSE) down -v

.PHONY: profile
profile:
	mkdir -p profile/results && \
	docker compose down -v && \
	$(PROFILE_COMPOSE) up --build  --remove-orphans--abort-on-container-exit --attach profiler || \
	$(PROFILE_COMPOSE) down -v

.PHONY: dev
dev:
	docker compose down -v && \
	docker compose up -d --force-recreate --build  --remove-orphans