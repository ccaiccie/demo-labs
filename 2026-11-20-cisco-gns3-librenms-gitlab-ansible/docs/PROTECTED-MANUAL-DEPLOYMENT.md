# Protected manual deployment: what ran and how to reproduce safely

The public default branch provides **automatic validation and review artifacts only**. It cannot change a router or switch. The recorded deployment was a separately reviewed, protected **manual** job on a dedicated local GitLab instance. It did not run repository-supplied code with device access.

## Evidence from the recording lab

| Step | Result |
|---|---|
| MR validation, pipeline 7 | Native playbook syntax passed; 16 unit tests; 12 downloadable review files. No device access. |
| First protected gate, pipeline 8 / job 9 | Guard syntax error; rejected before any device write. Not deployment evidence. |
| Corrected protected gate, pipeline 9 / job 10 | Manually approved one-shot run on `lab-deploy-v2`, reviewed commit `3ec9e7b6`. No standing authorization or automatic retry. |

The corrected job targeted only `lab-r1`, a Cisco IOSv router, and only the description on its disconnected, administratively down `GigabitEthernet0/2`. Adoption was zero changes; review predicted one; apply changed one; independent SSH confirmed the exact new description; the identical module repeat changed zero; rollback changed one; independent readback confirmed the original description and admin-down state. There was no startup save. This particular GitLab deployment proof did **not** change the switch. The switch was verified separately through the native Ansible exercise.

The fixed one-shot controller and the public Ansible exercise are **not interchangeable**. The public playbook intentionally refuses a repeated apply when the original baseline no longer matches. Zero-change repeat evidence in the recorded gate came from an explicitly bounded repeat check using the already-changed baseline, not bypassing the public playbook's guard.

## Setup sequence for your own isolated guest

1. Follow [GitLab, Runner and Ansible from scratch](GITLAB-ANSIBLE-INSTALL.md). Establish an isolated validation runner and prove its successful validation/render jobs before considering device access.
2. Keep deployment on a **different trust path**. Create a protected branch/ref restricted to approved maintainers, and a protected/tagged runner or equivalent fixed dispatcher usable only by that ref. If your GitLab edition does not support your required approval controls, stop at the guest-local manual Ansible exercise. Do not expose a generic shell/deploy runner to branch or MR jobs.
3. Place the deployment controller outside the repository and outside validation-worker access. Review and pin its executable and allowed inputs through your private change procedure. It should accept only the exact approved pipeline/job/ref/revision/action and its one allowed device/interface/before/after tuple. Reject missing, expired, already-used, or mismatched approvals; fail closed before SSH. Do not pass arbitrary repository scripts, shell arguments, inventory paths, Ansible variables, or unsigned rendered artifacts into this controller.
4. Supply your own private runner configuration, verified host keys, dedicated least-privilege device credential, and inventory **inside the guest**. Keep them out of Git, GitLab job output, artifacts and recording. The public example inventory uses documentation IPs and deliberately cannot be used live.
5. Make the deployment action manual. Protect the ref and runner, restrict who can trigger it, and keep automatic validation and credential-bearing execution separate. Review the exact diff and rollback snapshot beforehand. Test negative guard cases with no device writes before the first live job. The configured policy, not merely a YAML `when: manual` label, is the access boundary.
6. In one disposable lab run, adopt without writes, predict the approved delta, apply the one description, independently verify running state, repeat the same bounded operation to prove zero changes, roll back, and independently verify the original and interface state. On unexpected state, stop and investigate. Never publish the raw transcript or config, and do not add an automatic retry.
7. Disable the deployment runner and revoke the temporary runner authentication when the evidence is captured.

No registration token, working controller, runner driver, production deployment template or private inventory is shipped here. The safe portable path is [the command companion](COMMAND-COMPANION.md): run the reviewed commands in your own guest, after matching them to your own lab. See GitLab's [protected runners](https://docs.gitlab.com/ci/runners/configure_runners/), [manual jobs](https://docs.gitlab.com/ci/jobs/job_control/) and [custom executor](https://docs.gitlab.com/runner/executors/custom/). GitLab lists the custom executor in maintenance mode. The recorded temporary custom executor was suitable only for a disposable single-owner demonstration, not a hardened or multi-tenant runner.
