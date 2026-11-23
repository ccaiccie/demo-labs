# Prompts Used in This Lab

1. Build a complete, beginner-friendly, narrated demo: "Using Terraform with NetBox to standardize network and firewall configuration."
   - Environment: MYDELL2. Install everything needed locally (Docker, NetBox via netbox-docker, Terraform, the e-breuninger/netbox Terraform provider, and a lab firewall/router target). Log every install step.
   - Demo flow:
     1. What NetBox (source of truth) and Terraform (infrastructure as code) are, and why combine them.
     2. Stand up NetBox, then create a site, devices, interfaces, VLANs, prefixes and IPs with Terraform.
     3. Use NetBox data to generate standardized firewall configs: address objects, policies, and interface settings.
     4. Show drift: change something by hand, then run terraform plan and apply to fix it.
     5. Wrap up with a recap and common mistakes.
   - Requirements: Use real, working code (no placeholders), with each file shown and explained. Put all code in a folder with a README.
