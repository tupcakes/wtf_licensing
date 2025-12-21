#!/bin/bash

# Clean up and reset dev container
docker compose -f docker-compose-dev.yml down -v
docker buildx prune -f

# Start dev container with watch mode
docker compose -f docker-compose-dev.yml up --watch --build