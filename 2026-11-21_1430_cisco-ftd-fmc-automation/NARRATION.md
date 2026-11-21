# Narration script: "Configuring and automating FTD through FMC"

Each section matches what is on screen. Read it before or while the matching step runs.

## Intro (lab topology in GNS3)
In this demo we take two brand-new Cisco Secure Firewall Threat Defense virtual firewalls and manage them entirely from Firewall Management Center, without clicking through the GUI. Everything runs in one Ubuntu VM with GNS3. FMC and both firewalls sit on a management network, 192.168.100.0/24. Each firewall has an outside interface toward the internet and an inside interface protecting its own LAN, with an Ubuntu test PC on each LAN.

## Day-0 setup (consoles)
Each appliance first needs a minimal bootstrap from its console: accept the license agreement, set an admin password and a management IP. For the firewalls, we also choose to have them managed by FMC instead of locally. After this, everything else is done through the FMC REST API.

## Step 1 - Evaluation license
FMC won't accept firewalls until it has a license. For a lab, one API call turns on the 90-day evaluation mode.

## Step 2 - Shared objects
FMC config is object-based, so we build the reusable pieces first: an inside zone and an outside zone, an object for each inside LAN, an object for the upstream gateway, and an Access Control Policy whose default action is BLOCK. A firewall has to be given an access policy at the moment it is registered, so this comes first.

## Step 3 - Registration
Registration is a handshake. On the firewall we run "configure manager add" with the FMC address, a registration key and a NAT ID. Then we call the FMC API with the same key and NAT ID. FMC connects on TCP 8305, they exchange certificates, and the device appears in FMC. Watch "show managers": the status goes from Pending to Completed.

## Step 4 - Interfaces
Ethernet0/0 becomes "outside" with a static address on the upstream network and joins outside-zone. Ethernet0/1 becomes "inside", the default gateway for its LAN, and joins inside-zone. In the API this is a read-modify-write: get the interface, change it, PUT it back.

## Step 5 - Default route
Each firewall gets one static default route out the outside interface to 192.168.200.1.

## Step 6 - Access rule
One rule allows the inside LANs out to the outside zone, with logging, so the connections show up in FMC's event viewer. Everything else hits the default action, BLOCK.

## Step 7 - NAT
Private addresses can't be routed to the internet, so each inside LAN is hidden behind its firewall's outside address with dynamic interface PAT. The NAT policy is assigned to both firewalls.

## Step 8 - Deploy
Up to now, every change lives only in FMC's database. Deploy is what pushes it to the firewalls. We ask FMC which devices have pending changes, deploy to all of them in one request, and wait for the job to finish.

## Step 9 - Proof
From each test PC we ping 1.1.1.1 and load https://www.cisco.com. Both work. On the firewalls, the NAT translate_hits counters have gone up, which proves the traffic took the path we built: interface, route, access rule and NAT.

## Outro
Every step is idempotent. Run it again and it finds what already exists instead of creating duplicates. To build a different lab, edit lab.yaml.
