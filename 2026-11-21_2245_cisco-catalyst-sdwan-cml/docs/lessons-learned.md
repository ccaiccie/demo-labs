# Lessons learned while building this lab (20.18, config groups + policy groups)

These are real problems hit during the build, and how the code now avoids them.

1. **cloud-init YAML and Jinja whitespace** - a `-#}` comment end ate the next line's
   indentation; the Manager booted with factory defaults. Fixed with `#}` and the
   build now validates every rendered YAML before importing the lab.
2. **"Cannot delete management vpn 512"** - every controller needs VPN 512 in its
   bootstrap, even when only the Manager uses it.
3. **Policy group: "Please configure the VPN's CORP in your configuration-groups"** -
   policies reference a VPN by the **name of its feature parcel** in the service
   profile (`LAB-VPN10-CORP`), not by the VPN number and not by the `name` field
   inside the parcel. The GUI's VPN picker reads
   `GET /v1/feature-profile/sdwan/service/features?featureType=lan/vpn`.
   `policy.vpn_ref()` builds that exact name.
4. **"SLA class is not configured with fallback-tunnel criteria"** - an AAR rule
   with *fallback to best path* needs `fallbackBestTunnel` in the SLA class.
5. **"Overlapping apply-policy site-list"** - a mesh parcel for VPN 10 and a
   hub-and-spoke parcel for VPN 20 both become control policies on the same branch
   sites; the Controller allows only one per site and direction. VPN 10 needs no
   parcel at all (no control policy = full mesh).
6. **Built-in hub-and-spoke rejects everything else** - it also hid VPN 10 routes
   and branch-to-branch TLOCs. Replaced by one *custom control* parcel
   (`GUEST-ISOLATION`) that only filters VPN 20 routes, default accept.
7. **Order inside step 9** - the Controller's generated config embeds the policy
   group, so the policy content is built/updated first, then the topology group is
   deployed, then the policy group.
8. **Console** - edges land at `Router>`; `Console.run(enable=True)` sends `enable`.
