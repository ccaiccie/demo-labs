# LibreNMS and Oxidized: dedicated GNS3 guest

**Scope:** a dedicated Ubuntu 24.04 lab guest only. These files are an
installation recipe, not an installer or a live test report. Do not run them
on the hypervisor. Preserve any pre-existing guests. Native Ubuntu packages avoid another
container stack; use a single small PHP-FPM pool, a 128 MiB MariaDB buffer pool
and two Oxidized workers. Watch memory and swap on the guest with GitLab
and the routers running; do not add CI runners to this first recording.

| Service | Bind/target | Purpose |
| --- | --- | --- |
| LibreNMS | `127.0.0.1:8081` | Guest-only web GUI |
| MariaDB | `127.0.0.1:3306` and Unix socket | Guest-local LibreNMS DB |
| Oxidized | `127.0.0.1:8888` | Guest-local API, may expose backed-up configs |
| IOSv router | `192.0.2.10` | Verify address, image and management port |
| IOSv-L2 switch | `192.0.2.11` | Verify address, image and management port |
| Guest-side veth | `192.0.2.1/24` | Only permitted device polling/SSH origin |

Preflight: check `hostname`, `systemd-detect-virt`, `ip -br addr`,
`ip route`, `free -h`, `df -h /var /opt` and `sudo ss -lntup`.
These are RFC 5737 documentation placeholders, not working targets. Substitute your own isolated management subnet and verify it before use. Confirm management reaches only the
two intended nodes on the guest-private veth/GNS3 Cloud link. Do not attach a
physical bridge, GNS3 NAT node, or a router management default route. Keep guest
forwarding off and do not broadly open firewall rules. Use only licensed IOS
images already authorized for the lab.

## 1. Pin and stage

- LibreNMS [26.10.0 composer manifest](https://raw.githubusercontent.com/librenms/librenms/26.10.0/composer.json)
  allows PHP ^8.2; stock Noble ships PHP 8.3. [26.11.0](https://raw.githubusercontent.com/librenms/librenms/26.11.0/composer.json)
  requires PHP ^8.4; don't use it with stock Noble PHP. This is an isolated
  compatibility pin, not a production upgrade or security recommendation.
- Oxidized [0.38.0](https://github.com/ytti/oxidized/releases/tag/0.38.0)
  and [oxidized-web 0.18.1](https://rubygems.org/gems/oxidized-web/versions/0.18.1)
  are explicitly pinned in the Gemfile. Verify actual Ruby and Bundler versions
  and preserve the resolved lockfile. Record LibreNMS commit and installed
  package versions. Don't use an unreviewed install script or public browser
  access.
- APT packages, the checkout, Composer dependencies and gems need an approved
  staging source: either fetch in a temporary guest staging window or carry
  verified offline artifacts/cache. Keep the dashboard and monitoring sockets
  closed on any staging NIC. Disconnect/remove the staging path and verify
  no default route before recording or adding device credentials. The package
  install may auto-start stock nginx, which normally binds all interfaces.
  Perform package installation while disconnected if staged; otherwise use an
  already enforced guest firewall denying inbound on the staging NIC while
  installing, remove the stock site immediately, then disconnect. Do not
  change host firewall/services for this.

## 2. LibreNMS native setup

Use [LibreNMS's install instructions](https://docs.librenms.org/Installation/Install-LibreNMS/)
and the recipe below for the lab-specific bind and resource limits. Start in
the directory containing this README. Stop if a file or path belongs to an
existing deployment.

```bash
sudo apt install acl curl fping git mariadb-client mariadb-server mtr-tiny nginx-full \
  nmap php-cli php-curl php-fpm php-gd php-gmp php-json php-mbstring php-mysql \
  php-snmp php-xml php-zip python3-command-runner python3-dotenv python3-pip \
  python3-psutil python3-pymysql python3-redis python3-setuptools python3-systemd \
  rrdtool snmp traceroute unzip whois
php -v
sudo systemctl stop nginx
# Remove this stock symlink only if it is confirmed to be Ubuntu's unused default.
if [ -L /etc/nginx/sites-enabled/default ] && \
   [ "$(readlink -f /etc/nginx/sites-enabled/default)" = /etc/nginx/sites-available/default ]; then
  sudo unlink /etc/nginx/sites-enabled/default
fi
sudo useradd librenms -d /opt/librenms -M -r -s "$(command -v bash)"
sudo git clone --branch 26.10.0 --single-branch https://github.com/librenms/librenms.git /opt/librenms
sudo chown -R librenms:librenms /opt/librenms
sudo chmod 0771 /opt/librenms
sudo setfacl -d -m g::rwx /opt/librenms/{rrd,logs,bootstrap/cache,storage}
sudo setfacl -R -m g::rwx /opt/librenms/{rrd,logs,bootstrap/cache,storage}
sudo -u librenms git -C /opt/librenms rev-parse HEAD
sudo -u librenms -H /opt/librenms/scripts/composer_wrapper.php install --no-dev
sudo install -m 0644 librenms-nginx.conf /etc/nginx/sites-available/librenms-lab.conf
sudo ln -s /etc/nginx/sites-available/librenms-lab.conf /etc/nginx/sites-enabled/librenms-lab.conf
sudo install -m 0644 librenms-fpm.conf /etc/php/8.3/fpm/pool.d/librenms.conf
sudo install -m 0644 librenms-mariadb.cnf /etc/mysql/mariadb.conf.d/60-librenms-lab.cnf
sudo /usr/sbin/php-fpm8.3 -t
sudo nginx -t
sudo systemctl restart mariadb php8.3-fpm
sudo systemctl start nginx
sudo ss -lntup
```

The `clone` and Composer fetch are staging operations; use a verified local
checkout and cached dependencies if disconnected. Use local MariaDB Unix-socket authentication for administrative SQL. Off-camera, start `sudo env MYSQL_HISTFILE=/dev/null mariadb`,
then use the pinned vendor DB steps. Replace `PRIVATE_DB_PASSWORD` with an
independent generated value; never type it into a recorded terminal or shell
argument.

```sql
CREATE DATABASE librenms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'librenms'@'localhost' IDENTIFIED BY 'PRIVATE_DB_PASSWORD';
GRANT ALL PRIVILEGES ON librenms.* TO 'librenms'@'localhost';
EXIT;
```

Inside the guest browse to `http://127.0.0.1:8081/install`. Use the local
DB account with host `localhost` and create a dedicated lab UI administrator.
Keep setup/password entry off camera. Confirm installed app and administrator
login, retaining only safe screenshots. Set the deployed pin to not
auto-update before enabling scheduled jobs when the setting is available
(`sudo -u librenms -H /opt/librenms/lnms config:set update false`); verify
the effective configuration and that the checkout remains at the expected
commit. Do **not** override PHP platform checks or silently update the checkout.

Enable the official scheduler/service after the UI installs successfully:
```bash
sudo cp /opt/librenms/dist/librenms-scheduler.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now librenms-scheduler.timer
sudo -u librenms -H /opt/librenms/validate.php
systemctl list-timers librenms-scheduler.timer
```

Install the checkout's `dist/librenms.cron` and `misc/librenms.logrotate`
only as directed by the pinned docs; inspect cron for update/poller tasks
and avoid duplicate pollers if a dispatcher is used. Never fix a failed
validate by granting world permissions or binding to all addresses.

## 3. Poll IOSv/IOSv-L2, SNMPv3 only

Using the guest GNS3 consoles, verify the IOSv and IOSv-L2 image commands,
management interface/IP and a default-deny management path first. Configure
a dedicated per-device SNMPv3 authPriv user, SHA authentication and AES-128
privacy when accepted by both selected images. Use the read-only group and
restrict polling to the guest address; skip optional trap settings. Confirm
the exact ACL syntax with the current IOS help before applying. Example
shape only, with the password lines entered off camera:

```text
ip access-list standard LAB-NMS
 permit host 192.0.2.1
snmp-server view LAB-NMS-READ iso included
snmp-server group LAB-NMS v3 priv read LAB-NMS-READ access LAB-NMS
snmp-server user LAB-POLL LAB-NMS v3 auth sha PRIVATE_AUTH priv aes 128 PRIVATE_PRIV
```

Use distinct secrets with compatible lengths. Confirm `show snmp user` and
authPriv polling without revealing secrets. Add each address in guest
LibreNMS Devices → Add Device; choose v3, authPriv, SHA and AES. Prefer
credential entry in the guest UI to a command-line SNMP invocation with
passwords visible via process arguments. Test discovery, wait for scheduled
poll cycles, and verify the real last-polled timestamp and interface counters.
No claim of working graphs until at least two actual samples exist. If the
switch routing/SVI is down, inspect port/VLAN state instead of guessing.
Do not loosen the management ACL or fall back to a community string merely
to get the UI green. [SNMP examples](https://docs.librenms.org/Support/SNMP-Configuration-Examples/).

## 4. Oxidized: guest-local only

Stage dependencies, create a dedicated account, and lock the raw storage:
```bash
sudo apt install ruby ruby-dev ruby-bundler build-essential libssl-dev \
  libssh2-1-dev pkg-config libyaml-dev zlib1g-dev
command -v bundle
sudo useradd -r -U -m -d /var/lib/oxidized -s /usr/sbin/nologin oxidized
sudo chmod 0700 /var/lib/oxidized
sudo install -d -m 0750 -o root -g oxidized /etc/oxidized
sudo install -d -m 0755 /opt/oxidized
sudo install -m 0644 oxidized.Gemfile /opt/oxidized/Gemfile
( cd /opt/oxidized && sudo bundle config set --local path vendor/bundle && sudo bundle install )
sudo install -m 0640 -o root -g oxidized router.db.example /etc/oxidized/router.db
sudo install -m 0640 -o root -g oxidized oxidized-config.yml.example /etc/oxidized/config
```

Off camera, populate private config with a dedicated SSH account and verified
credential, using different per-node credentials in private CSV mapping if
needed. Keep secure host-key verification enabled. Obtain expected lab
router/switch host key fingerprints from the local consoles or approved
baseline, compare them to offered SSH keys, then pin both public keys into
`/var/lib/oxidized/.ssh/known_hosts` writable only by the service user.
The config template uses password authentication; a separately staged
dedicated lab SSH key is preferable if supported by the IOS images. Use
the minimum read privilege required by the model, no shared admin
credential. If older lab images cannot negotiate modern SSH, repair or
restrict an exception to the dedicated lab service and exact hosts after
review; don't disable host verification or loosen SSH globally.

Look up the actual bundle path and validate it against `ExecStart`.
After editing the private config:
```bash
if sudo grep -q 'REPLACE_' /etc/oxidized/config; then
  printf '%s\n' 'STOP: private settings have not been configured' >&2
  exit 1
fi
sudo install -m 0644 oxidized.service /etc/systemd/system/oxidized.service
sudo systemd-analyze verify /etc/systemd/system/oxidized.service
sudo systemctl daemon-reload
sudo systemctl enable --now oxidized.service
sudo ss -lntp
# Check only the HTTP status instead of printing potentially sensitive JSON.
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8888/nodes.json
```

If the private raw repository is successfully created, keep it under
`/var/lib/oxidized`, never link/push/copy it into the GitLab project.
`remove_secret` is model-specific and incomplete. Do not film the raw diff,
device backup API body, terminal output of `show running-config`, or the
LibreNMS Configs tab's raw config. Use [the local LibreNMS integration](https://docs.librenms.org/Extensions/Oxidized/)
only after accepting that authenticated guest LibreNMS users may see raw
configs. For the first demo, configure `oxidized.enabled=true` and
`oxidized.url=http://127.0.0.1:8888` in the local UI if needed (no LibreNMS API
token required for the file-based node source). Check that LibreNMS device
names match Oxidized node names. Don't configure webhooks or any remote push.

## 5. Export safe description evidence, independently

Capture only `show interfaces description` for the verified practice port,
off-camera to a private local file. Confirm the port is a non-management,
non-control-link Gi0/2 and the approved values still match this checkout.
Do not run commands where command authorization or target is unclear.
The example exporter below reads only stdin, rejects unknown/ambiguous
values, and doesn't write or publish anything:

```bash
umask 077
tmp=$(mktemp)
if python3 export_description.py lab-r1 < /PRIVATE/PATH/iosv-descriptions.txt > "$tmp"; then
  cat "$tmp" # only fixed fields + exact allowlisted description
else
  printf '%s\n' 'No description exported; inspect input privately.' >&2
fi
rm -f -- "$tmp"
```

Repeat independently on the verified switch. Inspect only the resulting
description-only JSON and put a **reviewed** copy in the desired state's
evidence area if requested. The existing starter's fixture parser accepts
synthetic examples only: these live JSON outputs are separate evidence, do
not replace synthetic fixtures or assert a plan passed. Diff only approved
texts before any commit; don't stage raw files, secrets, host keys or
runtime inventory. Never film credential entry, credential files, raw
configuration payloads or API response bodies.

## Runtime gates still pending

Record actual version/commit and listener bindings, UI login, meaningful
polls, two successful private backups, then a safe description-only before
and after. If native services fail, check private logs off-camera and
report the actual stage. Stop services or restore a verified **guest-only**
checkpoint to revert; don't remove database/storage with an existing
deployment. No automated device changes, git pushes, or host changes here.

Official detail: [Oxidized pinned config](https://github.com/ytti/oxidized/blob/0.38.0/docs/Configuration.md),
[pinned inputs](https://github.com/ytti/oxidized/blob/0.38.0/docs/Inputs.md)
and [pinned output](https://github.com/ytti/oxidized/blob/0.38.0/docs/Outputs.md).
