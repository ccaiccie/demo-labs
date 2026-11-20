# Dedicated-guest Cisco manual-first adoption and change

Not executed. No router/switch image or interface has been live-verified by this scaffold.

## 1. Manual baseline first

Inside the dedicated Ubuntu VM, build isolated GNS3 IOSv routers and IOSv-L2 switches from the licensed images. Configure topology/connectivity/management manually; verify before adopting under Ansible/GitLab. Do not bridge management to production.

Coordinate actual interface names. GigabitEthernet0/2 is an illustrative non-management practice port on each fixture, not a claim about your images. Use one router and one switch initially. Do not infer Catalyst/IOS XE switch compatibility.

Confirm:
- approved image/version and IOS CLI supports the selected commands;
- existing SSH management and a lab account authorized for configuration;
- independently verified SSH host keys, no host-key bypass;
- router's selected port has description PRACTICE-LINK and switch's has PRACTICE-SWITCH;
- no other operator changes this slice during the demonstration.

Do not create permissions/AAA or alter management in this playbook. The sample assumes the existing approved lab login has the required privilege. Keep credentials in an approved agent/secret store, never inventory or Git. Network devices do not need Python installed.

Capture a restricted full backup outside Git. Review/sanitize the managed description slice. The committed evidence is synthetic: replace/adapt it only as a separately reviewed adoption step. Desired adoption must match captured baseline exactly.

## 2. Guest-only tools and syntax validation

Install an approved compatible ansible-core plus official cisco.ios and ansible.netcommon collections inside the guest; pin resolved versions after compatibility testing. requirements.yml names collections but does not claim a tested version lock.

From that guest working copy:
```bash
ansible-playbook -i ansible/inventory.example.yml ansible/description.yml --syntax-check
```
This is pending. Local YAML parsing alone does not validate module availability or playbook semantics.

Create a local inventory outside Git with verified isolated addresses and identities. Documentation addresses 192.0.2.10/.11 are blocked by guards. Controller uses ansible.netcommon.network_cli and cisco.ios.ios, not Linux shell/vtysh.

## 3. No-op adoption and review, one target at a time

These are **network-connected read/dry-run operations**, not offline tests, and need approved targets. Restrict every invocation to one device; the playbook rejects a multi-target run.

```bash
# First adopt the manually configured router unchanged:
ansible-playbook -i /secure/lab-inventory.yml ansible/description.yml --limit lab-r1 \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e operation=adopt

# Repeat adoption for the switch:
ansible-playbook -i /secure/lab-inventory.yml ansible/description.yml --limit lab-sw1 \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e operation=adopt

# Review the router proposal; ios_config is forced into check mode:
ansible-playbook -i /secure/lab-inventory.yml ansible/description.yml --limit lab-r1 --check \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e operation=review
```

Repeat review with --limit lab-sw1. Adoption asserts ios_config proposes no changes. The baseline guard rejects divergence rather than silently reconciling it. The playbook outputs only a bounded description summary; raw configuration/module details use no_log.

## 4. Apply only approved description and verify

After separate review/approval, substitute lab-sw1 to perform its own approved switch change:
```bash
ansible-playbook -i /secure/lab-inventory.yml ansible/description.yml --limit lab-r1 \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e execute_lab_change=true -e operation=apply
```

Only ios_config parents interface GigabitEthernet0/2 and one description line are sent. save_when=never. Readback verifies the description within the selected interface stanza. Check monitoring labels and demonstrate unchanged forwarding separately. No success is claimed until live verification completes.

## 5. Revert and verify

```bash
ansible-playbook -i /secure/lab-inventory.yml ansible/description.yml --limit lab-r1 \
  -e allow_lab_read=true -e dedicated_ubuntu_vm_confirmed=true \
  -e exact_interface_confirmed=true -e execute_lab_change=true -e operation=rollback
```

Repeat for lab-sw1. Rollback requires the expected changed baseline and restores only the original description; it then reads back and verifies. It does not restore entire configuration or save startup state. If anything diverges, stop and review rather than forcing the rollback. A failed verification has no automatic rollback.

Never turn on verbose secret-bearing callbacks or publish raw device configuration. Consent flags do not protect against an attacker who can edit playbooks; VM isolation, SSH authorization and review enforce the actual boundary.

## Example addressing

The documentation-only subnet 192.0.2.0/24 illustrates a guest/controller at .1, router at .10 and switch at .11. Choose an isolated lab management subnet with no overlap and substitute your own verified addresses. The shipped inventory deliberately blocks both example targets.
