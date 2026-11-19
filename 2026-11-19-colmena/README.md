# Colmena: stateless NixOS deployments for network engineers

Lab for the Network Technician video of 2026-11-19. Three NixOS "network appliances" run as Docker containers
on an internal network, and [Colmena](https://github.com/zhaofengli/colmena) deploys them from one `hive.nix`:

| Node | Address | Tag | What Colmena deploys |
|---|---|---|---|
| router1 | 10.88.0.11 | `@edge` | nftables firewall plus an `edge` table with a blocklist set, a dummy SNMP key |
| dns1 | 10.88.0.12 | `@dns` | Unbound resolver serving the `lab.` zone from `data/dns-records.json` |
| monitor1 | 10.88.0.13 | `@monitoring` | Prometheus scraping node_exporter on all three (UI on 127.0.0.1:9095) |

Every node also gets SSH (key only), node_exporter on port 9100 (allowed only from 10.88.0.0/24), and dig, tcpdump and curl.

The last part adds a governed GitOps flow, inspired by Li Yang's talk
[Building Agent-Ready Infrastructure with NixOS, GitOps & AI](https://www.youtube.com/watch?v=Onk6yW7GTkw&t=628s):
a chat request in n8n goes to OpenAI, which only translates it into a structured intent. `changebot/changebot.py`
turns the intent into a commit on a branch, `ci/check.sh` runs a policy check and `colmena build`, and only a passing
branch is merged and deployed with `colmena apply`. The AI never touches a server.

## Files

| Path | Purpose |
|---|---|
| `hive.nix` | The Colmena hive: `meta`, `defaults` and one entry per node (final state from the video) |
| `data/dns-records.json`, `data/firewall.json` | Data the hive reads: DNS records for dns1, extra open ports per node |
| `nixpkgs.nix` | Pinned nixpkgs (nixos-26.05 channel commit) |
| `nodes/container-base.nix` | Shared NixOS base: runs as a Docker container with systemd, sshd with the lab key |
| `image/default.nix` | Builds the bootstrap image (`docker import` of a NixOS system tarball) |
| `nodes/up.sh`, `nodes/down.sh` | Start or remove the three nodes on the `colmena-lab` Docker network (10.88.0.0/24) |
| `ssh_config` | SSH settings for 10.88.0.* (lab key, root, accept-new host keys) |
| `lab-shell` | Shell with Colmena 0.4.0 from the pinned nixpkgs, through nix-portable |
| `ci/policy.py`, `ci/check.sh` | CI gate: policy check of the data change, then `colmena build --on <node>` |
| `changebot/changebot.py` | Branch, commit, CI, merge and `colmena apply` for one AI intent (HTTP on port 8091) |
| `n8n/colmena-change-request.json` | Separate n8n workflow: Chat Trigger, OpenAI "Message a model", HTTP Request, Reply |
| `reset.sh` | Puts this lab back to its starting state (only these containers) |

## Run it

Needs Docker and WSL2 or Linux. No root is needed for Nix: the video uses
[nix-portable](https://github.com/DavHau/nix-portable), because the official installer needs sudo to create `/nix`.
On a machine where you have sudo, the official installer and `nix shell nixpkgs#colmena` work the same way.

```bash
curl -L -o ~/bin/nix-portable https://github.com/DavHau/nix-portable/releases/download/v012/nix-portable-x86_64
chmod +x ~/bin/nix-portable
ssh-keygen -t ed25519 -N '' -f keys/lab_ed25519           # lab-only key, gitignored
NP_RUNTIME=bwrap ~/bin/nix-portable nix-build image/default.nix -o result
docker import result/tarball/nixos-system-*.tar.xz colmena-lab/nixos-base:26.05
# put the image's system path in nodes/base-system.txt (readlink of /init inside the image), then:
nodes/up.sh
./lab-shell                                                  # prompt changes to (colmena)
mkdir -p secrets && echo lab-demo-community-not-a-secret > secrets/snmp-community.txt
colmena apply                                                # all nodes in parallel
colmena apply --on @dns                                      # only nodes tagged dns
colmena exec -- systemctl --failed                           # run a command on every node
dig router1.lab @10.88.0.12
```

Rollback, from the video: every `colmena apply` makes a new system generation on the node, so

```bash
colmena exec -- "nix-env -p /nix/var/nix/profiles/system --rollback && /nix/var/nix/profiles/system/bin/switch-to-configuration switch"
git revert --no-edit HEAD    # make the hive match what is running again
```

GitOps part: import `n8n/colmena-change-request.json` into n8n, select your own OpenAI credential, publish it, and run
`./lab-shell 'python3 -u changebot/changebot.py 172.28.0.1'` (the gateway of the n8n Docker network). Open the chat
URL shown on the Chat Trigger node and ask, for example, "add a DNS record for app1 pointing to 10.88.0.50".

## Troubleshooting (all seen in the video or while preparing it)

| Symptom | Cause | Fix |
|---|---|---|
| `nftables.service` fails: `fib saddr . mark . iif oif exists accept` | The WSL2 kernel has no nftables fib support, used by NixOS reverse path filtering | `networking.firewall.checkReversePath = false;` |
| systemd exits with `Failed to create /init.scope control group: Read-only file system` | Docker mounts the cgroup filesystem read-only | `nodes/up.sh` remounts it read-write before `/init` (needs SYS_ADMIN, not `--privileged`) |
| `prometheus.service` fails: `Failed to set up user namespacing` | The unit asks for PrivateUsers, which an unprivileged container cannot create | `systemd.services.prometheus.serviceConfig.PrivateUsers = lib.mkForce false;` |
| `dig` to dns1 times out | Port 53 was not open in the node's nftables firewall | add 53 to dns1 in `data/firewall.json` |
| `dig` to dns1 returns `status: REFUSED` | Unbound only answers localhost by default | `access-control = [ "10.88.0.0/24 allow" ];` |
| `could not create symlink /etc/hosts` during activation | Docker bind-mounts /etc/hosts and /etc/hostname | Harmless in containers |
| `evaluation warning: 'system' has been renamed` | Printed by Colmena 0.4.0's evaluator with the new nixpkgs | Harmless |

## Safety notes

- Everything stays on an internal Docker network (10.88.0.0/24); the only published port is Prometheus on 127.0.0.1:9095.
- The SSH key, the known_hosts file and `secrets/` are gitignored. The SNMP community is a dummy value.
- Colmena keys are uploaded over SSH at deploy time and are not stored in the Nix store.
- The AI step only produces an intent. The policy (allowed ports, lab IP range, protected records, one node per change)
  and the build decide, and a person can review the rejected branch.

## Clean up

```bash
nodes/down.sh
docker rmi colmena-lab/nixos-base:26.05
```
