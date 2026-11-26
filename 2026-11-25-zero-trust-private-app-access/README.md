# Practice Lab — Three-Cloud Zero-Trust Private App Access Comparison

Intended repository path: `ccaiccie/demo-labs/2026-11-25-zero-trust-private-app-access`

This compact practice lab provides a **comparable zero-trust private-app path** in each of the three clouds so you can compare **identity source**, **policy enforcement**, and **client requirements** hands-on:

1. **AWS Verified Access (`aws-verified-access.tf`)** — Identity: AWS IAM Identity Center (AWS Organizations instance, same Region) • Policy: Cedar on Verified Access Group • Client: Browser (no VPN client).
2. **Google Cloud IAP (`gcp-iap.tf`)** — Identity: Google Identity • Policy: IAM (`roles/iap.httpsResourceAccessor` + `roles/iap.tunnelResourceAccessor` with `destination.port == 22`) + `35.235.240.0/20` VPC firewall • Client: Browser (HTTPS) / `gcloud` CLI (TCP forwarding).
3. **Microsoft Entra Private Access (`entra-private-access-cli.md`)** — Identity: Microsoft Entra ID • Policy: Conditional Access on Quick Access or Per-App Global Secure Access enterprise app • Client: Global Secure Access Client + Private Network Connector.

## Official Documentation Sources
- AWS Verified Access: https://docs.aws.amazon.com/verified-access/latest/ug/what-is-verified-access.html
- Microsoft Entra Private Access: https://learn.microsoft.com/en-us/entra/global-secure-access/concept-private-access
- Microsoft Global Secure Access overview: https://learn.microsoft.com/en-us/entra/global-secure-access/overview-what-is-global-secure-access
- Google Cloud Identity-Aware Proxy: https://cloud.google.com/iap/docs/concepts-overview
- Google Cloud IAP TCP forwarding: https://cloud.google.com/iap/docs/tcp-forwarding-overview

## Honest Prerequisites (Do Not Skip)
- **AWS path (`enable_aws = true`):** Requires an existing **AWS Organizations instance of IAM Identity Center** in the same Region, an existing **internal ALB**, subnets (max 1/AZ), security group, and a public **ACM TLS certificate** matching your application domain. Hourly per-app Verified Access charges apply.
- **GCP path (`enable_gcp = true`):** Requires an existing **Google Cloud project** with billing, `compute.googleapis.com`, and `iap.googleapis.com` enabled, plus a Google Account / Group email.
- **Microsoft Entra path (`entra-private-access-cli.md`):** Requires **Microsoft Entra ID P1 or P2** + **Microsoft Entra Private Access** (standalone or **Microsoft Entra Suite**), a Windows Server host inside your private network for the **Microsoft Entra private network connector**, and the **Global Secure Access Client** installed on your test endpoint.

## 1. Deploy AWS and/or GCP Paths with Terraform
```bash
cp terraform.tfvars.example terraform.tfvars
# Toggle enable_aws = true and/or enable_gcp = true and fill in your real IDs
terraform init
terraform plan -out tfplan
terraform apply tfplan
```

## 2. Walk Through Microsoft Entra Private Access
Follow [entra-private-access-cli.md](./entra-private-access-cli.md) to deploy the Private Network Connector, configure Quick Access or a Per-App Global Secure Access app, attach a Conditional Access policy, and test with the Global Secure Access Client.

## 3. Destroy & Clean Up Everything
- **AWS & GCP (Terraform):**
  ```bash
  terraform destroy
  ```
  (Remove any public DNS CNAME record created for AWS Verified Access.)
- **Microsoft Entra Private Access:** Follow the cleanup steps at the bottom of `entra-private-access-cli.md` to disable the Conditional Access policy, delete the Global Secure Access enterprise app, and uninstall the Private Network Connector.
