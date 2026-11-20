# GitLab CE, Runner and Ansible from scratch

## Where this runs

Use a disposable Ubuntu 24.04 (Noble) amd64 guest. Keep the GitLab UI on guest loopback, and never give the validation runner a route to lab management or access to the controller's files, SSH credentials or hypervisor. Do not install a shared runner for unknown projects. The versions below record the walkthrough, not a recommendation to use historical packages on public-facing infrastructure.

The fresh setup footage used an additional offline Noble root filesystem **inside the dedicated guest**, booted using systemd-nspawn with `--private-network --resolv-conf=off --timezone=off`. Packages were staged ahead of time. The exact fresh package transaction, run as root inside that scratch container, was `apt-get -y --no-download --no-install-recommends install gitlab-ce=19.6.0-ce.0 ansible-core=2.16.3-0ubuntu2 iproute2`. That scratch instance used manual reconfigure and a loopback-only listener at port 8186; it was not the existing operational instance at port 8929 that served the pipeline. The scratch Ansible package demonstrates the core install; install the Ubuntu `ansible` package for the bundled lab collections as described below. This preserved the working demo instance. The recording contains no public GitLab deployment. A staging package download and a disconnected install are separate steps.

## 1. GitLab Community Edition

Inside the disposable guest, follow the [official Ubuntu Linux-package setup](https://docs.gitlab.com/install/package/ubuntu/) and add the **Community Edition** repository. Review the repository bootstrap script before executing it. Use the local HTTP URL only for the isolated lab. Example after setting up the approved repository and staging the packages:

```bash
sudo env EXTERNAL_URL=http://127.0.0.1:8929 apt install gitlab-ce=19.6.0-ce.0
dpkg-query -W gitlab-ce
sudo gitlab-ctl status
```

For a disconnected install, the same version and its dependencies need to be present in the local APT source/cache. Do not reuse a GitLab data directory from an existing instance. Verify the listener is loopback-only before adding credentials or private files; if the default listener is broader, configure and verify the Linux package's NGINX listen addresses before using the service. Open the address **from inside the guest** and complete initial admin setup off camera. Create your own private lab project and copy this folder's contents to its root so GitLab sees `.gitlab-ci.yml`.

## 2. Ansible and native syntax

Install the Ubuntu Ansible package, not only ansible-core: the playbook needs the Cisco IOS and netcommon collections. The recorded guest had Ansible 9.2.0 / ansible-core 2.16.3 with `cisco.ios` 5.3.0 and `ansible.netcommon` 5.3.0. Check availability and record exact package revisions; do not silently upgrade collections.

```bash
sudo apt install ansible
LC_ALL=C.UTF-8 ansible --version
LC_ALL=C.UTF-8 ansible-galaxy collection list
LC_ALL=C.UTF-8 ansible-playbook -i ansible/inventory.example.yml ansible/description.yml --syntax-check
```

Run the syntax check from the project root. It does not connect to devices. See [Ansible distribution installation](https://docs.ansible.com/projects/ansible/latest/installation_guide/installation_distros.html) and the [command companion](COMMAND-COMPANION.md) for the separately authorized live lab actions.

## 3. Runner binary and isolation

The walkthrough used GitLab Runner **19.6.0**, downloaded as the [official Linux amd64 standalone binary](https://s3.dualstack.us-east-1.amazonaws.com/gitlab-runner-downloads/v19.6.0/binaries/gitlab-runner-linux-amd64). Follow [GitLab's manual installation instructions](https://docs.gitlab.com/runner/install/linux-manually/) for your platform. Verify the binary before staging against the [upstream release checksum](https://s3.dualstack.us-east-1.amazonaws.com/gitlab-runner-downloads/v19.6.0/release.sha256). The downloaded binary was checked against that checksum before use. Its SHA-256 was `295f0d264b540286e1d1ede2bd572f890269e2a4977c7a656a3f71280845bc2f`.

Create a project runner through the GitLab UI and retain its runner authentication token in approved private storage, never in the repo, a command capture or a job artifact. See [runner registration](https://docs.gitlab.com/runner/register/). Use the `offline-guest` tag for validation.

The original runner was a temporary foreground custom executor, not a host service, Docker executor or persistent unattended agent. The trusted runner manager did local GitLab fetch/upload. Project code ran unprivileged, without capabilities, and in a separate no-network namespace. Do not replace that boundary with a normal shell runner on the controller. To reproduce the validation with a different executor, separately verify that project jobs cannot read controller files/credentials, use privileged services, or reach lab management. No CI job needs a device key, inventory or route.

## 4. Separate validation and deployment

- **Automatic validation:** the recorded MR-source pipeline on an Ansible file change passed native syntax, 16 unit tests and rendering. It produced 12 review files across adoption/proposal and both devices. This checkout adds an optional YAML/Jinja regression; its local test count may differ. Rendering generates artifacts only.
- **Protected manual deployment:** a separate corrected and manually approved one-shot job successfully applied and then restored a single router description. The first gate attempt failed closed and made no change. See [the isolated deployment walkthrough](PROTECTED-MANUAL-DEPLOYMENT.md) for verified boundaries, evidence and setup steps. The public CI definition cannot run a deployment.
