.PHONY: setup dev agent console api frontend livekit token lint format typecheck test check

# Defaults (lowercase — matches colon-style keys)
room     := test-room
identity := user1
ttl      := 24h
mode     := dev

# Parse colon-style args: make token room:my-room identity:alice
$(foreach a,$(filter-out $(.PHONY),$(MAKECMDGOALS)),\
  $(if $(findstring :,$(a)),$(eval $(subst :, := ,$(a)))))

# Silently ignore colon args so Make doesn't treat them as targets
.DEFAULT:
	@:

## Setup ——————————————————————————————————————————————
setup: ## Install all dependencies
	uv sync
	cd frontend && npm install

## Services ————————————————————————————————————————————
dev: ## Start all 4 services (livekit, agent, api, frontend)
	@bash scripts/dev.sh

agent: ## Start the LiveKit agent
	uv run python -m src.war_room_copilot.core.agent dev

console: ## Start agent in console mode (no browser needed)
	uv run python -m src.war_room_copilot.core.agent console

api: ## Start the API server
	uv run python -m src.war_room_copilot.api.main

frontend: ## Start the dashboard dev server
	cd frontend && npm run dev

livekit: ## Start LiveKit server (make livekit mode:prod)
ifeq ($(mode),prod)
	livekit-server --config /etc/livekit.yaml
else
	livekit-server --dev --bind 0.0.0.0
endif

token: ## Generate a room token (make token room:my-room identity:alice ttl:1h)
	lk token create --api-key devkey --api-secret secret --join --room $(room) --identity $(identity) --valid-for $(ttl)

## Code Quality ————————————————————————————————————————
lint: ## Lint with auto-fix
	uv run ruff check src/ --fix

format: ## Format code
	uv run ruff format src/

typecheck: ## Type checking
	uv run mypy src/

test: ## Run tests
	uv run pytest tests/ -v

check: lint format typecheck test ## Run full quality pipeline
