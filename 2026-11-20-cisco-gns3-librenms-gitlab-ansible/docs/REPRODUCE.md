# Reproduce the lab

1. Create a dedicated Ubuntu VM. Install GNS3 using [GNS3 documentation](https://docs.gns3.com/) and provide your own properly licensed Cisco IOSv and IOSv-L2 images. Build an isolated lab management segment; do not bridge it to a production network.
2. Configure the router and switch manually. Validate management and choose an unused Gi0/2 (or adapt the reviewed demo consistently). The verification lab left Gi0/2 administratively down on both nodes. Do not perform this exercise on a management or uplink port.
3. Add monitoring separately using the [LibreNMS/Oxidized guide](../deploy/monitoring/README.md). Confirm successful polling; keep raw backup history private. Observed evidence is not desired intent.
4. Use the [command companion](COMMAND-COMPANION.md) to run offline tests and render the no-op adoption / proposal. Review change, baseline digest and rollback per device before considering a write.
5. If using GitLab, copy **the contents of this dated folder** to the root of a separate private lab GitLab project so its `.gitlab-ci.yml` appears at the project root. The parent public repository does not automatically run nested CI definitions. Use an isolated runner with no device credentials or management network route; there is no deploy job. Do not commit real configs/inventory. An MR-specific reusable example needs its own source branch/revision and is not a prerequisite to use this starter.
6. In the dedicated guest only, use an approved private inventory and perform native Ansible syntax, no-op adoption and review. Apply only the reviewed description, verify readback, then roll back and verify both original values. No startup-save occurs.

This is a reproducible starter and teaching companion, not a bootable VM/appliance or a copy of the recording environment. Exact image compatibility, interface names, SSH authentication, CI setup and monitoring installation must be validated in your own guest.

For the optional, separate GitLab deployment demonstration, see [protected manual deployment](PROTECTED-MANUAL-DEPLOYMENT.md). It requires your own reviewed local controller and runner controls, not a change to this public CI template.
