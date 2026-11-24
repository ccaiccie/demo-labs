# Cisco FTD through FMC: full automated build with Python and the REST API

One Python script takes an empty Firewall Management Center (FMCv 10.0.1) and two blank Secure Firewall Threat Defense virtual firewalls (FTDv 10.0.0 for KVM) and turns them into a working two-site setup that passes real traffic to the internet. All of it runs through the FMC REST API: licensing, zones and objects, device registration, interfaces, routing, access control, NAT, deployment, and a live traffic test. Every step is idempotent, so you can safely run the script again.

Video: [Cisco FTD through FMC: Full Automated Build with Python and the REST API (Explained)](https://youtu.be/id3nwWRsNZ0)

Related video: [Cisco Catalyst SD-WAN on CML – A to Z: Full Python Build, Policies and Failover](https://youtu.be/RY-a3hQxlnA)

## Lab topology (GNS3)

| Device | Management | Outside (Ethernet0/0) | Inside (Ethernet0/1) | Test PC |
|---|---|---|---|---|
| FMC | 192.168.100.10 | - | - | - |
| FTD1 | 192.168.100.11 | 192.168.200.11/24 | 10.1.1.1/24 | Ubuntu-Test-1, 10.1.1.10 |
| FTD2 | 192.168.100.12 | 192.168.200.12/24 | 10.2.2.1/24 | Ubuntu-Test-2, 10.2.2.10 |

- The GNS3 project has 11 nodes: FMC, FTD1, FTD2, two Ubuntu test-PC containers, and the switches and clouds that connect them.
- `br-mgmt` (192.168.100.0/24) is the management network. `br-outside` (192.168.200.1/24) is the upstream gateway, NATed to the internet by the host.
- Host used for the recording: Ubuntu 24.04 VM with 54 GB RAM and 12 vCPU. FMCv uses 32 GB, and each FTDv uses 8 GB and 4 vCPU. With less than about 50 GB, FMC won't start.

## Files

| File | What it does |
|---|---|
| `lab.yaml` | The lab definition. Change addresses or names here, not in the code. |
| `fmc_client.py` | Minimal FMC API client: token login and refresh, retries on HTTP 429 rate limits, paging, get-or-create. |
| `narrate.py` | Prints the viewer-facing explanation before each step. |
| `demo.py` | The nine build steps. |
| `reset.py` | Removes everything `demo.py` built, so the build can be recorded from scratch. |
| `record_build.sh` | Records the full build as an asciinema cast. |
| `rec2/` | Helpers used to record the video segments: the lab tour, curl API calls, FTD CLI checks, and the re-run. |
| `NARRATION.md` | Narration notes for each step. |
| `lab-secrets.env.example` | Template for the secrets file. |

## The nine steps

1. Turn on the FMC evaluation license.
2. Create security zones, network and host objects, and an Access Control Policy with default action BLOCK.
3. Register FTD1 and FTD2: run `configure manager add` over SSH, then `POST devices/devicerecords`, and wait for the registration task.
4. Configure the outside and inside interfaces with their names, zones and IPs.
5. Add a default static route via 192.168.200.1 on outside.
6. Add the access rule Allow-Inside-to-Outside, logging at connection end.
7. Create the NAT policy with dynamic interface PAT for each inside LAN, and assign it to both FTDs.
8. Deploy, track the job, and repeat until nothing is pending.
9. Verify: each test PC pings 1.1.1.1 and fetches https://www.cisco.com, then the FTD NAT hit counters and connection table are checked.

## Setup

Prerequisites:
- FMCv and two FTDv nodes already bootstrapped (day 0): management IPs, admin password set, and FTDs set to be managed by FMC.
- Python 3 with the packages in `requirements.txt`.
- The script runs on the GNS3 host, because step 9 uses `docker exec` on the test-PC containers.

```bash
git clone https://github.com/ccaiccie/demo-labs.git
cp -r demo-labs/2026-11-21_1430_cisco-ftd-fmc-automation /root/ftd-automation
cd /root/ftd-automation
pip install -r requirements.txt
cp lab-secrets.env.example /root/lab-secrets.env && chmod 600 /root/lab-secrets.env
# edit /root/lab-secrets.env and set LAB_ADMIN_PW and LAB_REG_KEY
```

The admin password and registration key are read only from `/root/lab-secrets.env`. They are never stored in this folder, and the registration key is masked in the output.

## Run

```bash
python3 demo.py                 # all nine steps (safe to re-run)
python3 demo.py --step 9        # one step
DEMO_PAUSE=1 python3 demo.py    # recording mode: waits for Enter before each step
python3 reset.py                # wipe the FMC config and unregister the FTDs
```

## Notes and lessons learned

- **Same account in the GUI and the API:** don't log in to the FMC GUI with the same account while a script is using the API. That can invalidate the API token partway through a run.
- **Re-runs still deploy once:** step 4 always PUTs the interfaces, so FMC marks the devices as changed and step 8 deploys again. To skip that, compare each interface first and only PUT when a value differs.
- **Rate limit:** FMC allows about 120 API requests per minute, and `fmc_client.py` retries on HTTP 429.
- **Startup time:** FMCv takes roughly 10 to 25 minutes to boot before the API answers. `POST /api/fmc_platform/v1/auth/generatetoken` returning 401 without credentials means the API is up.
- **API Explorer:** the interactive explorer is at `https://<fmc>/api/api-explorer/`, and the trailing slash matters.
