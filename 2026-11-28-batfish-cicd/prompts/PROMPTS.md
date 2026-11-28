# Prompts Log

## Prompt 1

> Demo Batfish (batfish.org) as a local network CI/CD lab on this Windows + WSL Docker machine, in this workspace folder only. Angle: a local Git repo of FRR-style or Cisco IOS-style router configs (3-4 made-up routers, OSPF/BGP, one edge ACL) with Batfish run as a pre-merge pipeline: a GitHub Actions-style workflow file (.github/workflows/batfish.yml) plus a plain local runner script (ci/run_pipeline.sh) that mirrors the workflow steps, running pybatfish pytest checks against the snapshot. Show a good change passing, then three bad changes on branches that the pipeline catches: (1) an ACL edit that blocks a needed flow (searchFilters / testFilters), (2) a BGP peer AS or neighbor IP mismatch (bgpSessionCompatibility / bgpSessionStatus), (3) a missing route caught by reachability/traceroute. Then fix each and show the pipeline pass again. Keep the Git history (main + feature branches + merges) as evidence.
