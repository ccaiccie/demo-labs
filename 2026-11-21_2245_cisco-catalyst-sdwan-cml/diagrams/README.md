# Concept diagrams

The diagrams shown in the video, as editable draw.io files using the Cisco 19 stencil set
(open them in draw.io desktop or app.diagrams.net).

| File | Concept |
|---|---|
| why1 / why2 | The traditional WAN problem and the four SD-WAN ideas |
| comp / comp2 | Manager, Controller, Validator, WAN edges; lab vs. production |
| planes / conn | Orchestration, management, control and data planes; DTLS, IPsec and key distribution |
| vpns / vpns2 | VPN 0, 512, 10 and 20; full mesh vs. guest topology |
| tloc / restrict | TLOCs and colours; the restrict option |
| omp / ctrlpol | OMP route types, the Controller as route reflector, control policy |
| bfd / aar | BFD probes, buckets and app-aware routing decisions |
| onboard / trust | Zero-touch onboarding sequence and the trust chain |
| cg / cg2 / pg / goals | Configuration groups, policy and topology groups |
| underlay / steps | The Gateway router's VRFs and the nine build steps |
| dia / iso / hs | GUEST-DIA, GUEST-ISOLATION and the hub-and-spoke lesson |
| walk / fail / vrrp | Packet walk, MPLS failover and VRRP router-failure tests |

`gen.py` (with `dlib.py`) generates all of them, including the build-up stages used in the video:

```bash
python3 gen.py          # writes src/*.drawio and exports png/*.png
```

Export uses draw.io desktop headless: `xvfb-run -a drawio -x -f png -o out.png in.drawio`.

## Setup-scene topology map

During the code walkthrough (parts 3 and 4) and the live build (parts 5 and 6), the video shows a
side panel next to the code or terminal: a 9-step progress bar and a mini-map of the lab topology,
with the parts the current file or step touches highlighted as the narration mentions them.

- `smap.py` builds the map (`python3 smap.py edge tun` writes `src/sm_edge_tun.drawio` and its PNG;
  no arguments = everything at full colour). Tags: `you mgmt ca serial cg pol cml mgr val ctl vpn0 gw
  inet mpls tun sites edge hosts v10 v20`, plus any site (`DC`, `BR1`...), router (`BR1-E1`) or host (`BR2-PC`).
- `setup-map/smapdef.py` lists, for every setup scene, which tags light up at which sentence, and what the
  progress bar shows (`use` = file is used by those steps, `run` = that step is running).
- `setup-map/panel.py` draws the 450x790 panel (progress bar + map).
- `setup-map/topology-map.drawio` is the full map, editable in draw.io.
