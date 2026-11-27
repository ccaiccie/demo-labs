# Netlab Local Demo Lab Runbook

Operational commands for running the `netlab-demo` OSPF + BGP lab in WSL Ubuntu 24.04 with `containerlab` and free `frr` + `linux` images.

## Prerequisites

- Windows with WSL `Ubuntu-24.04` and a running Docker daemon.
- `netlab`, `containerlab`, `ansible`, `graphviz`, and `sshpass` installed via:
  ```bash
  sudo bash scripts/install-netlab.sh
  ```

## Topology Summary

- **Lab name / container prefix**: `netlab-demo` (`clab-netlab-demo-*`)
- **Provider**: `clab` (Containerlab)
- **Images**: Free open-source `frr` and `linux` images only; no host ports are published.
- **Autonomous Systems**:
  - `AS 65001`: `r1`, `r2`, `r3` (OSPFv2 area 0 + iBGP)
  - `AS 65002`: `r4` (eBGP peering with both `r2` and `r3`)
  - Hosts: `h1` (attached to `r1`), `h2` (attached to `r4`)
- **Addressing**:
  - Loopbacks: `192.0.2.0/24` (`/32` per router)
  - Point-to-point links: `198.51.100.0/24` (`/30` per link)
  - Host stub LANs: `203.0.113.0/24` (`/28` per LAN)
  - Management bridge (`netlab-demo-mgmt`): `192.168.250.0/24` (non-colliding RFC 1918 Docker bridge)

## Lifecycle Commands

Run all commands from this lab directory inside WSL `Ubuntu-24.04`:

1. **Preview addressing plan (optional, before boot):**
   ```bash
   netlab report addressing
   ```

2. **Start the lab:**
   ```bash
   netlab up
   ```

3. **Check lab status and inspect generated topology state:**
   ```bash
   netlab status
   netlab inspect
   ```

4. **Connect to nodes and run `show` / host commands:**
   ```bash
   netlab connect r1 -- vtysh -c "show ip ospf neighbor"
   netlab connect r2 -- vtysh -c "show ip bgp summary"
   netlab connect r4 -- vtysh -c "show ip route"
   netlab connect h1 -- ip -brief addr
   netlab connect h1 -- ping -c 3 203.0.113.22
   ```

5. **Run automated validation tests:**
   ```bash
   netlab validate
   ```

6. **Failure and recovery scenario (shut down primary eBGP link `r2`–`r4`):**
   ```bash
   # Shut down the r2->r4 interface on r2
   netlab connect r2 -- vtysh -c "configure terminal" -c "interface eth3" -c "shutdown"
   # Validate: ebgp_as65002 on r2 fails while r3->r4 and ping_h1_h2 still pass
   netlab validate || true
   # Restore the interface
   netlab connect r2 -- vtysh -c "configure terminal" -c "interface eth3" -c "no shutdown"
   # Re-validate: all checks pass again
   netlab validate
   ```

7. **Generate topology graph (light background):**
   ```bash
   netlab graph topology.dot
   dot -Tsvg -Gbgcolor=white topology.dot -o topology.svg
   dot -Tpng -Gbgcolor=white topology.dot -o topology.png
   ```

8. **Tear down the lab cleanly:**
   ```bash
   netlab down --cleanup
   ```
   Verify no `clab-netlab-demo-*` containers remain:
   ```bash
   docker ps -a --filter "name=clab-netlab-demo"
   ```
