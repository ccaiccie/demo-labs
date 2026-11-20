---
name: replay-check
description: >-
  Run unit tests, verify the Docker service is up, replay sample syslog events
  with the replayer, and query the REST API to summarize open incidents. Use
  this skill when verifying the NetOps incident bot end-to-end.
---

# Replay Check

End-to-end verification workflow for the NetOps incident bot.

## Steps

1. **Run unit tests**
   - Execute the `unittest` suite from the repository root:
     ```bash
     python -m unittest discover
     ```
   - Stop and report any test failures before proceeding.

2. **Check that the Docker service is up**
   - Verify the container(s) are running:
     ```bash
     docker compose ps
     ```
   - Confirm the service is reachable on `http://127.0.0.1:8097` (for example, via its health or status endpoint). If the service is not running, report it rather than silently skipping.

3. **Replay sample logs**
   - Run the project's syslog replayer against `127.0.0.1:5515` (UDP) using the sample log dataset.
   - Verify the replayer exits cleanly and reports the number of events sent.

4. **Query the REST API and summarize open incidents**
   - Query the open incidents endpoint on `http://127.0.0.1:8097`.
   - Summarize the returned open incidents clearly (total count, IDs/titles, severity, affected made-up hostnames/documentation IPs, and current state).
   - Never print or log any secrets or API keys if authentication headers are used.
