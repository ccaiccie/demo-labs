# Cisco walkthrough: command companion

Use this alongside the walkthrough, not as authorization to change another network. All network operations belong inside the dedicated Ubuntu lab guest. Nothing here installs software, pushes Git, merges a request, or runs a CI deployment.

## Verified scope

| Inventory alias | Device role | Practice interface | Original → demonstration description |
|---|---|---|---|
| `lab-r1` | Cisco IOSv router | `GigabitEthernet0/2` | `PRACTICE-LINK` → `PRACTICE-LINK reviewed demo` |
| `lab-sw1` | Cisco IOSv-L2 switch | `GigabitEthernet0/2` | `PRACTICE-SWITCH` → `PRACTICE-SWITCH reviewed demo` |

Both interfaces were administratively down before and after verification. No interface-state, IP, VLAN or routing changes were made. These results do not establish support for Catalyst hardware or other IOS XE switches.

## Local files first: no device contact

Run from the patched starter repository root:

```bash
python3 scripts/render.py --check
python3 scripts/render.py --change --check
python3 -m unittest discover -s tests -v
```

`desired/` contains adopted state: both plans report `changed=False`. `changes/` contains the two proposed descriptions: both report `changed=True`. These are synthetic local fixtures, not live observations. Tests include the YAML/Jinja regression only when those parser dependencies are available.

To create local review files, without deployment:

```bash
python3 scripts/render.py
python3 scripts/render.py --change
```

Outputs are under `build/adoption/<alias>/` and `build/proposal/<alias>/`: `change.cli`, `rollback.cli`, `review.json`. Rendering proves neither device reachability nor CI success.

## Native Ansible syntax, then one device at a time

The guest must already have compatible Ansible/Cisco collections, approved inventory and authentication, and verified SSH host keys. Set `INVENTORY` to your approved inventory file in that guest before continuing. Its location and credentials are deliberately not included here. Do not use the shipped documentation-only addresses for a live run.

```bash
ansible-playbook -i ansible/inventory.example.yml ansible/description.yml --syntax-check
```

For the router, select `lab-r1`; later repeat the same full cycle with `lab-sw1`. These commands use the exact verified playbook options:

```bash
TARGET=lab-r1
ansible-playbook -i "${INVENTORY:?Set approved lab inventory first}" ansible/description.yml --limit "$TARGET" \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e operation=adopt
```

Expected adoption: `changed=0`. This contacts the device and checks the manual baseline, but forces the configuration module into check mode.

```bash
ansible-playbook -i "${INVENTORY:?Set approved lab inventory first}" ansible/description.yml --limit "$TARGET" \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e operation=review
```

Expected review: predicts one change, **does not apply it**. After reviewing and authorizing that exact description change:

```bash
ansible-playbook -i "${INVENTORY:?Set approved lab inventory first}" ansible/description.yml --limit "$TARGET" \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e execute_lab_change=true -e operation=apply
```

Expected apply: one change and successful exact-description readback. Restore the original description after the demonstration:

```bash
ansible-playbook -i "${INVENTORY:?Set approved lab inventory first}" ansible/description.yml --limit "$TARGET" \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e execute_lab_change=true -e operation=rollback
```

Expected rollback: one change and successful original-description readback. There is no startup-save or automatic rollback. If a guard fails, stop; do not weaken it. Select `TARGET=lab-sw1` and repeat adoption through rollback separately.

## What the proof does and does not mean

The direct guest verification exercised both devices, restored both originals and independently confirmed both ports remained administratively down. An identical second `ios_config` operation produced zero changes in a separate bounded verification harness.

**Do not confuse that with rerunning this whole playbook:** a second `operation=apply` intentionally refuses because its original-baseline guard no longer matches. That refusal is not a successful idempotent run. The private verification harness is not a reusable command included in this starter. Captured terminal output or its replay shows a particular run, not a new execution on playback.

## Optional merge-request examples

The commands above match the patched baseline `ansible/description.yml`, not an arbitrary MR branch. If the walkthrough shows an optional reusable script or different playbook from a particular merge request, use that MR's source branch/revision and its own instructions. Do not assume it exists on the default branch or in an older archive. This companion provides no unverified checkout command or CI-success claim and does not replace any archive.

Checked against the patched example playbook and local fixtures on 2026-11-20. Playbook SHA-256: `849a3a4706ea350b0222ea21d0ac9b58a4f63518c51a7f392de943deb99b749f`.
