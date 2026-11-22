# Cisco Secure Firewall (FTD/FMC) advanced security, configured in the GUI and tested from a real desktop

This lesson turns on the advanced security features of Cisco Secure Firewall Threat Defense (FTDv 10.0.0), one at a time, through the Firewall Management Center (FMCv 10.0.1) web GUI. No scripts and no API are used. Each feature is then tested live from the Ubuntu-Test-1 desktop behind FTD1 (over VNC), and the result is read in FMC Unified Events.

Video: [Cisco FTD/FMC Advanced Security A to Z: IPS, URL, App Control, SI, File and TLS Decryption (GUI)](https://youtu.be/AxF6rYnOWXg)

Prerequisite lab (the same GNS3 topology, built with Python and the FMC REST API): [2026-11-21_1430_cisco-ftd-fmc-automation](../2026-11-21_1430_cisco-ftd-fmc-automation/) and its video [Cisco FTD through FMC: Full Automated Build with Python and the REST API (Explained)](https://youtu.be/idqv28mOKuU).

## Lab

| Device | Management | Inside | Notes |
|---|---|---|---|
| FMC | 192.168.100.10 | - | FMCv 10.0.1, evaluation mode (not registered to Smart Licensing) |
| FTD1 | 192.168.100.11 | 10.1.1.1/24 | Outside 192.168.200.11, interface PAT to the internet |
| FTD2 | 192.168.100.12 | 10.2.2.1/24 | Outside 192.168.200.12 |
| Ubuntu-Test-1 | - | 10.1.1.10 | Desktop over VNC: Falkon browser and a terminal |

Starting point: one Access Control Policy, `Demo-ACP`, with rule `Allow-Inside-to-Outside` (inside-zone and the two inside networks to outside-zone) and default action Block All Traffic.

## The policy chain

A connection passes these stages in order, and any stage can stop it: Prefilter, Decryption, Security Intelligence, Identity, access control rules (applications and URLs), intrusion policy, then file and malware policy. Cheap checks run first. Deep inspection runs only on traffic an Allow rule permits.

## Part 0: licenses, cloud services and baseline

1. Devices > Device Management > FTD1 > Device tab > License (pencil). Tick Malware Defense, IPS and URL. Save. Repeat for FTD2.
2. Integrations > Cloud Services. URL Filtering is enabled with automatic updates (query source Cisco Cloud Only). AMP for Networks local malware detection updates are enabled.
3. Baseline from Ubuntu-Test-1: facebook.com, neverssl.com and the EICAR file over HTTPS all return HTTP 200.

## Part 1: Security Intelligence

1. Objects > Object Management > Security Intelligence > URL Lists and Feeds > Add. Name `Lab-SI-URL-Blocklist`, type List, upload a text file with `neverssl.com`, `www.neverssl.com`, `example.org`. The upload dialog showed 0 entries, but the saved object had all three. Check the saved object, not the dialog.
2. Network Lists and Feeds > Add. Name `Lab-SI-Net-Blocklist`, type List, with `9.9.9.9` and `149.112.112.112`.
3. Update Feeds (optional; fails on an unregistered FMC).
4. Demo-ACP > Security Intelligence. Add the network list and the URL list to the Block List. Logging is on. Save, then Deploy > Deploy All.
5. Test: `ping 9.9.9.9` gives 100% loss; `curl http://neverssl.com` gives HTTP 000 (a silent drop, so the browser just spins); cisco.com still returns 200.
6. Events & Logs > Unified Events: Security-Related Connection events with reason `IP Block` (9.9.9.9) and `URL Block` (neverssl.com). The access rule field shows Allow-Inside-to-Outside because SI dropped the traffic before that rule acted.

## Part 2: application control

1. Demo-ACP > Add Rule `Block-Social-Media-Apps`, action Block (with reset), inside-zone to outside-zone. Applications: Facebook, Instagram, TikTok. Logging at the beginning of the connection. Place it as rule 1, above the allow rule. Save and deploy.
2. Test: Facebook, Instagram and TikTok give HTTP 000 (connection reset); cisco.com gives 200. In Falkon, facebook.com cannot be reached.
3. Unified Events, filter Action = Block: web application Facebook / Instagram / TikTok, rule Block-Social-Media-Apps. This works on HTTPS without decryption because the server name is visible in the TLS handshake.

## Part 3: URL filtering, and a real troubleshooting case

1. Add Rule `Block-Risky-URL-Categories` (rule 2), action Block, inside-zone to outside-zone. URLs: categories Gambling and Adult, plus category Any with reputation 1 (Untrusted) and "apply to unknown reputation".
2. Policy warning after saving: enable TLS Server Identity Discovery. Fix: Demo-ACP > Advanced Settings > TLS Server Identity Discovery > Enhanced application and URL detection. Save and deploy.
3. Test: pokerstars.com and casino.org still return HTTP 200. Category filtering did nothing.
4. Troubleshooting:
   - Unified Events: the pokerstars connection is Allow, web application Pokerstars, URL present, but URL category and reputation are empty, and it matched rule 3.
   - Integrations > Cloud Services: last URL filtering update "Failed / Never". Update Now fails again.
   - Notifications > Health: Security Intelligence feeds failed, Talos connectivity failed, URL filtering monitor cloud lookup failure.
   - Root cause: the FMC is not registered to Cisco Smart Licensing, so it cannot reach the Talos cloud for the URL database or category lookups.
5. Workaround for the lab: in rule 2 > URLs, enter literal URLs `pokerstars.com` and `casino.org` (subdomains are covered). Save and deploy.
6. Test: both give HTTP 000; cisco.com 200. Unified Events shows rule Block-Risky-URL-Categories.

On a registered FMC, the category and reputation entries work without the literal URLs.

## Part 4: intrusion prevention (IPS)

1. Policies > Intrusion > Create Policy `Lab-IPS`, base Balanced Security and Connectivity, mode Prevention.
2. Snort 3 version > Rule Overrides: search `1:498` (INDICATOR-COMPROMISE id check returned root, content `uid=0(root)`). It is disabled in the base. Set the action to Block.
3. Demo-ACP > edit rule 3 Allow-Inside-to-Outside > Intrusion Policy `Lab-IPS`, variable set Default-Set. Save and deploy (Snort compiles the rules, so it takes longer).
4. Tests:
   - testmynids.org is now a parked domain, so it no longer returns `uid=0(root)`.
   - Sending the string in a POST to httpbin.org did not trigger the rule (the signature matches the server's response).
   - Making the server return the string does trigger it: `curl http://httpbin.org/base64/dWlkPTAocm9vdCkgZ2lkPTAocm9vdCkgZ3JvdXBzPTAocm9vdCkK` (response body `uid=0(root) gid=0(root) groups=0(root)`) gets no response: the packet is dropped. A control request to the same endpoint with harmless text (`/base64/aGVsbG8gZnJvbSB0aGUgbGFiCg==`, "hello from the lab") works.
5. Unified Events: an Intrusion event (Block) from 3.221.253.123:80 to 10.1.1.10, rule 1:498, MITRE ATT&CK Command and Control, Packet Info and Packet Bytes, and a Download PCAP button.

## Part 5: file and malware policy

1. Policies > Malware & File > New File Policy `Lab-File-Malware`.
   - Rule 1: protocol Any, direction Any, Block Files with reset, file type MSEXE.
   - Rule 2: Block Malware with reset, Local Malware Analysis, store files: Malware. Categories PDF files, Executables, Archive, Office Documents.
   - Advanced: Inspect Archives (max depth 2), Block Uninspectable Archives.
2. Demo-ACP rule 3 > File Policy `Lab-File-Malware`. Save and deploy. FMC warns that adding a file policy restarts Snort (inspect interruption).
3. Tests over HTTP: a small Windows executable is blocked (File event, MSEXE, connection reason File Block). The EICAR file is blocked too, but by the IPS first (rule 1:37732, POLICY-OTHER eicar test string download attempt). A normal text file passes.

## Part 6: TLS decryption, and re-testing over HTTPS

1. The gap: over HTTPS, putty.exe and the EICAR file both download with HTTP 200, because IPS and file policy see only encrypted bytes.
2. Objects > Object Management > PKI > Internal CAs > Generate CA `Lab-Decrypt-CA` (CN Lab Decryption CA), self-signed. Download it as a password-protected PKCS12 and copy it to Ubuntu-Test-1. In production, have your enterprise CA sign a CSR instead.
3. Policies > Decryption > Create Policy `Lab-Decrypt`. Outbound Decryption (Decrypt - Resign): inside-zone to outside-zone, CA Lab-Decrypt-CA, networks FTD1-Inside-Net and FTD2-Inside-Net. Keep the default bypasses (undecryptable applications; Finance, Online Trading, Health and Medicine). Block SSLv3, TLS 1.0 and 1.1, and invalid, expired or not-yet-valid certificates.
4. Demo-ACP > Decryption step > Lab-Decrypt (keep enhanced application and URL detection). Save and deploy.
5. Before the client trusts the CA: `openssl s_client` shows Issuer Lab Decryption CA, and `curl` fails with exit code 60.
6. Trust the CA on Ubuntu-Test-1:
   ```bash
   # run as root; -legacy is needed for the FMC PKCS12 export on OpenSSL 3
   openssl pkcs12 -legacy -in Lab-Decrypt-CA.p12 -nokeys -out /usr/local/share/ca-certificates/Lab-Decrypt-CA.crt
   update-ca-certificates   # "1 added"
   ```
7. Re-test: the control site returns 200. putty.exe stops at 1,703,954 of 1,706,136 bytes, and a retry shows `Connection reset by peer` (exit 56): connection reason File Resume Block. The EICAR file over HTTPS returns HTTP 000 with Intrusion, File and Malware (Malware Block) events. The connection details show TLS status Decrypt (Resign), TLS 1.3, certificate valid.

## Part 7: recap

Final Demo-ACP: Prefilter, Decryption, Security Intelligence and Access Control checked. Rule 1 blocks social media apps, rule 2 blocks risky URLs, rule 3 allows inside to outside with Lab-IPS and Lab-File-Malware attached, and the default action blocks everything else. One policy, deployed to two firewalls.

## Tips

- Save stores the policy in FMC. Nothing changes on the firewalls until you deploy.
- Rule order matters: top-down, first match wins.
- A Security Intelligence block is a silent drop; an access rule block with reset fails fast.
- When a test does not trigger, read the connection event (rule, category, inspection) before blaming the policy.
- URL categories, reputation and Talos feeds need a registered FMC with cloud connectivity.
- Decryption only works for users if their devices trust your CA. Push it before you enable the policy.

## Safety

All tests use harmless strings and the industry-standard EICAR test file. Everything ran inside a lab VM.
