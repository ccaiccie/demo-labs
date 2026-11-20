# 2026-11-20 Cisco GNS3 LibreNMS GitLab Ansible

**Public companion for an isolated brownfield lab.** Repository fixtures are synthetic and documentation IPs are placeholders. The recorded walkthrough and this checkout are separate: public fixtures are not captured device backups. All eventual deployed components, including GitLab and the Ansible controller, must run inside the dedicated Ubuntu VM, not directly on the hypervisor.

## Manual first, then adopt, then change

The intended lab mixes **Cisco IOSv routers and IOSv-L2 switches**. The two starter targets are one IOSv router (`lab-r1`) and one IOSv-L2 switch (`lab-sw1`). The files are synthetic baselines that match the bounded interface-description exercise. IOS XE switch/Catalyst hardware compatibility is not assumed. Confirm actual image versions, CLI behavior, and interface naming in the guest before live use.

1. Build and configure routers/switches manually in isolated GNS3 using licensed images.
2. Confirm connectivity and monitoring manually before automation.
3. LibreNMS observes device health/inventory. Optional Oxidized supplies configuration backups.
4. Capture a restricted baseline, sanitize and review its managed slice.
5. Adopt existing descriptions as desired intent: the first plan must show **zero changes**.
6. Propose one router and one switch description change in a reviewed merge request.
7. CI lints/tests/renders artifacts. Merge does **not** deploy.
8. Separately approve VM-only Ansible review/apply, one target at a time; verify and revert.

LibreNMS observations are not automatically written into desired intent. Full raw backups stay outside Git. This starter does not provision topology, install monitoring or import Cisco disks.

## Run offline

Requires Python 3.10+ standard library:
```bash
python3 scripts/render.py --check
python3 scripts/render.py --change --check
python3 -m unittest discover -s tests -v
python3 scripts/render.py
python3 scripts/render.py --change
```

- `observed/`: synthetic sanitized excerpts plus normalized baseline records.
- `desired/`: adopted router/switch descriptions equal to observations, hence no-op.
- `changes/`: separate reviewed proposal for each device.
- `build/adoption/<device>/`: no-op plan artifacts.
- `build/proposal/<device>/`: change.cli, rollback.cli, review.json.
- `ansible/description.yml`: official `cisco.ios.ios_config`, disabled until explicit guest/scope flags; defaults to no-op adoption.
- `docs/VM-EXECUTION.md`: manual-first workflow and guarded commands.
- `.gitlab-ci.yml`: lint/test/render only, no deployment.
- `.gitlab/merge_request_templates/Lab-description.md`: review checklist.

Both illustrative ports are `GigabitEthernet0/2`, **pending exact interface coordination**. They must be unused/identified non-management practice ports. Router proposal: `PRACTICE-LINK` → `PRACTICE-LINK reviewed demo`. Switch proposal: `PRACTICE-SWITCH` → `PRACTICE-SWITCH reviewed demo`.

No interface-state, VLAN, IP, routing, security or startup-save changes are included. Description changes can affect monitoring labels.

## GitLab later, inside the guest

Import into a private approved GitLab project only when requested. Nothing was pushed remotely here. Use the dedicated `offline-guest` runner with Python and Ansible collections staged, no device credentials, Docker socket or management-network access. No container image is pulled by this YAML. Artifacts expire after seven days. Protected branches/reviewers and runner isolation require operator setup; see the install guide.

## Validation status

**17 offline Python tests passed** using the system Python with PyYAML/Jinja2, compile/renderer checks passed, and YAML parsed. The YAML→Jinja regression checks both stanza templates with LF and CRLF. Without those optional dependencies, that test skips (16 pass, one skip), if the runner lacks those dependencies. Tests cover no-op adoption for both platforms, bounded proposals/rollback, injection, stale evidence, unknown fields, scope, and stanza extraction/guardrails.

**Packaging checks are offline.** The companion records native guest verification on the two demo images separately. That does not certify a new installation or other images. Run native syntax-check and approved dry-run in your own guest. The recorded counterpart auto-ran a merge-request validation pipeline after an Ansible change: native syntax, 16 unit tests and 12 review artifacts. That is evidence for that run, not a pipeline result for this public copy.

The Ansible example independently fixes the same before/after values as the JSON proposal. If the coordinated lab baseline changes, update and review the fixtures, hashes, playbook parameters and tests together; this scaffold does not automatically generate inventory or live variables from observed data.

## Safety limits

Exact synthetic fixture parser, not arbitrary device-config import. Baseline hashes detect accidental stale inputs, not malicious edits to both files. No credentials or full backups belong in Git; ignore rules are not secret scanning. The playbook flags are guardrails, not a security boundary. No automatic reconcile, automatic rollback or concurrent-editor lock.

## Official references
- [Cisco ios_config module](https://docs.ansible.com/projects/ansible/latest/collections/cisco/ios/ios_config_module.html)
- [GitLab CI syntax](https://docs.gitlab.com/ci/yaml/)
- [LibreNMS Oxidized integration](https://docs.librenms.org/Extensions/Oxidized/)

Checked 2026-11-20. FRR is no longer the demo default.

## Start here

- [Copyable command companion](docs/COMMAND-COMPANION.md): local rendering, native syntax, no-op adoption, review, apply, and rollback.
- [Guest-only execution guide](docs/VM-EXECUTION.md): manual-first prerequisites and verified-port checks.
- [LibreNMS and Oxidized example](deploy/monitoring/README.md): optional monitoring and private backup separation.
- [GitLab, Runner and Ansible installation](docs/GITLAB-ANSIBLE-INSTALL.md): isolated guest setup and evidence boundaries.
- [Protected manual deployment](docs/PROTECTED-MANUAL-DEPLOYMENT.md): exact recorded results and controller/runner separation; nothing deploys by default.
- [Reproduction checklist](docs/REPRODUCE.md): sequence from licensed images to the GitLab review.

Cisco image binaries and licenses are not distributed here. Obtain the images independently through an authorized Cisco entitlement and verify that your terms allow this use. No private inventories, SSH keys, service credentials, customer data, device backups, VM state, or live GitLab metadata are included.
