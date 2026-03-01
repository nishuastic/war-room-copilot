# Auto-detect LAN IP for LiveKit WebRTC on Docker Desktop for Mac.
# NODE_IP from .env is used as fallback; this override ensures it's always current.
NODE_IP ?= $(shell ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}')
export NODE_IP

ROOM ?= war-room

.PHONY: up down restart logs token kill-orphans playground dashboard demo demo-stop

# Kill orphaned Python workers from previous `dev` mode runs before starting
# Docker. These zombies connect to :7880 and steal jobs from the real agent.
kill-orphans:
	@./scripts/kill-orphan-workers.sh

up: kill-orphans
	@echo "NODE_IP=$(NODE_IP)"
	docker compose up --build

up-d: kill-orphans
	@echo "NODE_IP=$(NODE_IP)"
	docker compose up --build -d

down:
	docker compose down

restart: kill-orphans
	docker compose down && NODE_IP=$(NODE_IP) docker compose up -d

logs:
	docker compose logs -f agent

token:
	@docker compose exec agent python -c "\
	from livekit.api import AccessToken, VideoGrants; \
	t = AccessToken('devkey', 'secret'); \
	t.with_identity('user1'); \
	t.with_grants(VideoGrants(room_join=True, room='war-room')); \
	print(t.to_jwt())"

playground:
	@./scripts/open-playground.sh $(ROOM)

dashboard:
	@echo "Opening dashboard at http://localhost:3000"
	@open http://localhost:3000 2>/dev/null || echo "Open http://localhost:3000 in your browser"

# Demo mode: runs dashboard + scripted backend without LiveKit/MCP/API keys.
# Backend runs locally via uv; frontend via Docker (nginx proxy to host).
demo:
	@echo "Starting demo mode (no LiveKit required)..."
	@echo "  Backend: http://localhost:8000  (uvicorn + demo scenario)"
	@echo "  Frontend: http://localhost:3000  (nginx → backend)"
	@docker compose -f docker-compose.demo.yml up --build -d
	@uv run python -m war_room_copilot.api.demo_server &
	@sleep 2
	@open http://localhost:3000 2>/dev/null || echo "Open http://localhost:3000 in your browser"

demo-stop:
	@docker compose -f docker-compose.demo.yml down
	@pkill -f "war_room_copilot.api.demo_server" 2>/dev/null || true
	@echo "Demo stopped."
