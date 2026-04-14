TEST_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.test.yml
PERF_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.perf.yml
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
	docker compose up -d --force-recreate --build --remove-orphans

.PHONY: perf-baseline
perf-baseline:
	mkdir -p perf/results && \
	docker compose down -v && \
	PERF_SCENARIO=baseline $(PERF_COMPOSE) up --build --remove-orphans --abort-on-container-exit --attach perf || \
	$(PERF_COMPOSE) down -v

.PHONY: perf-stress
perf-stress:
	mkdir -p perf/results && \
	docker compose down -v && \
	PERF_SCENARIO=stress $(PERF_COMPOSE) up --build --remove-orphans --abort-on-container-exit --attach perf || \
	$(PERF_COMPOSE) down -v

.PHONY: perf-spike
perf-spike:
	mkdir -p perf/results && \
	docker compose down -v && \
	PERF_SCENARIO=spike $(PERF_COMPOSE) up --build --remove-orphans --abort-on-container-exit --attach perf || \
	$(PERF_COMPOSE) down -v
