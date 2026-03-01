# Auto-detect LAN IP for LiveKit WebRTC on Docker Desktop for Mac.
# NODE_IP from .env is used as fallback; this override ensures it's always current.
NODE_IP ?= $(shell ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}')
export NODE_IP

.PHONY: up down restart logs token

up:
	@echo "NODE_IP=$(NODE_IP)"
	docker compose up --build

up-d:
	@echo "NODE_IP=$(NODE_IP)"
	docker compose up --build -d

down:
	docker compose down

restart:
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
