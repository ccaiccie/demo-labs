#!/usr/bin/env bash
# Pull a small local model into the bifrost-ollama container.
set -euo pipefail
MODEL="${1:-llama3.2:1b}"
echo "Pulling $MODEL inside bifrost-ollama..."
docker exec bifrost-ollama ollama pull "$MODEL"
docker exec bifrost-ollama ollama list
