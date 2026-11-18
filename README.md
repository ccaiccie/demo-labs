# demo-labs

Labs that go with the Network Technician videos. Each folder is a self-contained lab you can run locally.

## Labs

| Lab | Description | Video |
|-----|-------------|-------|
| [2026-11-15-grafana-network-monitoring](2026-11-15-grafana-network-monitoring/) | Docker Compose lab: Grafana OSS, Prometheus, node_exporter, and blackbox_exporter for network monitoring. | [Grafana and Prometheus Network Monitoring Explained Step by Step](https://youtu.be/5CA2YiSQ_68) |
| [2026-11-16-zabbix](2026-11-16-zabbix/) | Docker Compose lab: Zabbix 7.0 LTS server, web (nginx), PostgreSQL, and two Zabbix agent 2 containers: fix the agent interface, add a host, items, triggers, problems, and a dashboard graph. | [Zabbix 7.0 LTS in Docker Step by Step: Hosts, Agents, Triggers, Problems and Dashboards](https://youtu.be/enb_ZUslzEY) |
| [2026-11-16-netbox](2026-11-16-netbox/) | Docker Compose lab: NetBox Community 4.7 with the official netbox-docker setup (netbox, worker, PostgreSQL, Valkey): sites, devices, interfaces, a cable and its trace, VLANs, prefixes, available IPs, tags, and the REST API with curl. | [NetBox in Docker Step by Step: Sites, Devices, Cables, IPAM and the REST API](https://youtu.be/pylHVnnSOUA) |
| [2026-11-16-librenms](2026-11-16-librenms/) | Docker Compose lab: LibreNMS 26.10.2 with the official librenms/docker setup (librenms, dispatcher, MariaDB, Redis) and two net-snmp + lldpd agents: SNMP v2c and v3 devices, discovery and polling with lnms, ports and traffic graphs, LLDP neighbours and the network map, health sensors, and an alert rule with an API webhook transport. | [LibreNMS in Docker Step by Step: SNMP v2c and v3, Discovery, Network Map and Alerts](https://youtu.be/14FF-ES6kPM) |
| [2026-11-17-netbox-automation](2026-11-17-netbox-automation/) | NetBox 4.7 as the source of truth: Ansible seeding, netbox.netbox dynamic inventory, Jinja2 FRR configs, two real OSPF routers, desired-state changes, live drift detection and repair, API next-available IP and an event webhook. | [NetBox Network Automation and IaC: Ansible, Jinja2, FRR Routers and Drift Detection](https://youtu.be/9zyP23RBq9I) |
| [2026-11-17-pentagi](2026-11-17-pentagi/) | Self-contained security lab: install the open-source PentAGI multi-agent AI pentest platform (VXControl) with Docker Compose, wire up a local OWASP Juice Shop practice target on the PentAGI worker network, and run an autonomous Automation flow against http://juiceshop:3000 - UI tour, OpenAI provider, Kali sandbox, Terminal, Agents, Searches, Screenshots and the Report, with honest notes on conservative results and human validation. | [PentAGI: Open-Source Multi-Agent AI Pentester, Hands-On in a Local Lab](https://youtu.be/c4eSTLnb6w0) |

## Courses and quizzes

- https://learn.techtohire.com
- https://quiz.techtohire.com
