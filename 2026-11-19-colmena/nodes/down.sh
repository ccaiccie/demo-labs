#!/usr/bin/env bash
# Removes the lab nodes and their network (only these containers).
docker rm -f router1 dns1 monitor1 2>/dev/null
docker network rm colmena-lab 2>/dev/null
true
