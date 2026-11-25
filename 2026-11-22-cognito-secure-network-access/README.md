# Amazon Cognito Secure Network Access — Terraform Practice Lab

Video: [Amazon Cognito Secure Network Access: ALB, API Gateway, WAF & PrivateLink (Nov 2026 + Lab)](https://youtu.be/dekqqfXOfAc)

> **Important Note — Validation Only:** This Terraform lab was initialized and verified with `terraform validate` using `hashicorp/aws` (`~> 6.0`). It was **not** applied to a live AWS account during preparation. Review all variables, prerequisites, and cost warnings below before running `terraform apply` in your own AWS account, and run `terraform destroy` as soon as you finish testing.

> **CIDR note:** The video's diagrams use `10.22.0.0/16` as an example; this lab defaults to `10.42.0.0/16`.

---

## What This Lab Builds

This lab demonstrates how a network and security engineer places **Amazon Cognito** in the path of application traffic across both public-edge and private VPC architectures:

| File | Resources Built | Purpose |
|---|---|---|
| `network.tf` | VPC (`enable_dns_support` + `enable_dns_hostnames`), 2 public subnets, 2 private subnets, Internet Gateway, NAT Gateway + EIP, route tables, security groups | Network foundation. The NAT Gateway enables an internal ALB (when `alb_internal = true`) or private workloads to reach Cognito's public IPv4 token and user-info endpoints. |
| `cognito_public_edge.tf` | `aws_cognito_user_pool.public_edge` (`ESSENTIALS`), `aws_cognito_user_pool_domain.public_edge` (Managed Login v2), ALB app client (`generate_secret = true`, `code` grant), API app client | Public-edge authentication pool for ALB `authenticate-cognito`, Managed Login, and API Gateway. |
| `cognito_private_link.tf` | `aws_cognito_user_pool.private_api` (**explicitly no domain**), Private M2M/API app client, Interface VPC Endpoints for `com.amazonaws.<region>.cognito-idp` and `com.amazonaws.<region>.cognito-identity` with private DNS and endpoint policies | Honest AWS PrivateLink pattern for direct Cognito SDK/REST API calls, `GetClientToken` M2M authorization, and Identity Pool API calls. |
| `cognito_identity_pool.tf` | `aws_cognito_identity_pool.main`, authenticated IAM role + minimal scoped policy, roles attachment | Contrasts **Identity Pools** (exchanging an identity token for temporary AWS STS credentials) against **User Pools** (sign-up/sign-in and JWT issuance). |
| `alb.tf` | Application Load Balancer, HTTP 80 → HTTPS 443 redirect listener, HTTPS 443 listener with `authenticate-cognito` + fixed response, `/app/*` forwarding rule + target group | Offloads user sign-in at the load balancer over HTTPS and forwards `X-AMZN-OIDC-*` identity headers to targets. |
| `apigateway.tf` | Regional REST API, `COGNITO_USER_POOLS` authorizer, `GET /protected` with MOCK integration, `v1` stage | Enforces Cognito JWT validation on REST API requests before backend execution. |
| `waf.tf` | Regional `aws_wafv2_web_acl` (IP rate limit, AWS Managed IP Reputation List, AWS Managed Common Rule Set) + associations to the public-edge Cognito User Pool, ALB (optional), and API Gateway stage (optional) | Layer 7 edge protection with explicit comments on what WAF can and cannot inspect on Cognito vs. API Gateway. |

---

## Why This Lab Uses Two Separate Cognito User Pools (PrivateLink Honesty)

Per the official [Amazon Cognito VPC Interface Endpoints documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/vpc-interface-endpoints.html):

1. **User pools with a domain assigned are incompatible with AWS PrivateLink.** The existence of a user pool domain prevents completion of any user-pool requests that transit an interface VPC endpoint.
2. **Managed login, the classic hosted UI, and OAuth 2.0 client-credentials requests to the token endpoint are not supported through PrivateLink.**
3. **Private DNS** on the `cognito-idp` interface endpoint routes `cognito-idp.<region>.amazonaws.com` to the endpoint ENIs — it does **not** route user-pool domain hostnames (`*.auth.<region>.amazoncognito.com` or custom domains).
4. **What IS supported through PrivateLink:**
   - Direct SDK / REST API calls (`InitiateAuth`, `AdminInitiateAuth`, `DescribeUserPool`, etc.) against a **domain-less** user pool.
   - Machine-to-machine (M2M) authorization using the **`GetClientToken` API** (which does not require a user pool domain).
   - Cognito **Identity Pool** SDK and REST API calls (`com.amazonaws.<region>.cognito-identity`).

Because ALB `authenticate-cognito` **requires** a user pool domain while PrivateLink **forbids** one, this lab keeps them cleanly separated:
- `aws_cognito_user_pool.public_edge` → has a Managed Login domain, used by ALB and API Gateway.
- `aws_cognito_user_pool.private_api` → has **no domain**, reachable over `aws_vpc_endpoint.cognito_idp`.

---

## Prerequisites

Before running `terraform plan` or `terraform apply` in your own AWS account:

1. **Terraform** `>= 1.6.0` installed locally.
2. **AWS CLI** configured with credentials that have permission to manage VPC, ELB, Cognito, API Gateway, WAFv2, and IAM resources.
3. **ACM Certificate (Required for ALB HTTPS):**
   - `authenticate-cognito` is supported **only on HTTPS listeners**.
   - Request and validate an AWS Certificate Manager (ACM) certificate in the **same Region** as `var.aws_region` before applying.
   - If you map a custom hostname (for example `app.example.com`) via Route 53 Alias/CNAME to the ALB, set `alb_fqdn = "app.example.com"` in `terraform.tfvars` so `https://app.example.com/oauth2/idpresponse` is added to the Cognito app client's `callback_urls`.
4. **Globally Unique Cognito Domain Prefix:**
   - Choose a unique lowercase value for `cognito_domain_prefix` in `terraform.tfvars`.

---

## How to Deploy

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your ACM certificate ARN, unique cognito_domain_prefix,
# and optionally restrict alb_ingress_cidrs to your public IP (/32).

terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

---

## Verification Steps (After `terraform apply`)

### 1. ALB `authenticate-cognito` (HTTPS)
1. Create a test user in the public-edge user pool (`aws cognito-idp admin-create-user` and `admin-set-user-password`).
2. Browse to `https://<alb_dns_name>/` (or `https://<alb_fqdn>/` matching your ACM certificate).
3. Verify the ALB redirects you (`302`) to the Cognito Managed Login page, and after sign-in redirects back to `/oauth2/idpresponse`, sets the `AWSELBAuthSessionCookie` cookie (`Secure`), and returns `200 OK` (`Authenticated at the ALB via Amazon Cognito.`).
4. Note: If you set `alb_internal = true`, test from inside the VPC (for example via Session Manager on an EC2 instance) and confirm the ALB reaches Cognito's public IPv4 token and user-info endpoints via the NAT Gateway.

### 2. API Gateway Cognito User Pool Authorizer
1. Call the protected endpoint **without** a token and confirm `401 Unauthorized`:
   ```bash
   curl -i "$(terraform output -raw api_gateway_protected_url)"
   ```
2. Authenticate against the public-edge pool's API client to obtain an **ID token** (remember: when `authorization_scopes` is unset on the API Gateway method, API Gateway validates an ID token):
   ```bash
   ID_TOKEN=$(aws cognito-idp initiate-auth \
     --auth-flow USER_PASSWORD_AUTH \
     --client-id "$(terraform output -raw api_app_client_id)" \
     --auth-parameters USERNAME=test@example.com,PASSWORD='<your-test-password>' \
     --query 'AuthenticationResult.IdToken' --output text)
   ```
3. Call the endpoint **with** the ID token and confirm `200 OK`:
   ```bash
   curl -i -H "Authorization: ${ID_TOKEN}" "$(terraform output -raw api_gateway_protected_url)"
   ```

### 3. AWS WAFv2 Boundaries & Evaluation Order
- Confirm the Web ACL is attached to the public-edge user pool, ALB, and API Gateway `v1` stage (`aws wafv2 list-resources-for-web-acl`).
- Remember the official AWS inspection boundaries:
  - **On Cognito User Pools:** WAF sees selected non-confidential headers and metadata only. **No PII** (usernames, passwords, email, phone) is ever forwarded to WAF. For **Managed Login and Classic Hosted UI**, the **request body is not forwarded** to WAF (body inspection applies only to user-pool API requests). WAF runs **before** Cognito API throttling, and `AWS-AWSManagedRulesATPRuleSet` cannot be attached to a Cognito User Pool.
  - **On API Gateway:** WAF is evaluated **before** the Cognito User Pool Authorizer and inspects headers, method, query string, URI, and the first 64 KB of the request body.

### 4. PrivateLink Interface VPC Endpoints (Domain-Less Pool)
From an EC2 instance or container inside a private subnet of the lab VPC:
1. Verify Private DNS resolves to a private VPC IP (`10.42.x.x`):
   ```bash
   dig +short cognito-idp.us-east-1.amazonaws.com
   dig +short cognito-identity.us-east-1.amazonaws.com
   ```
2. Call `DescribeUserPool` against the **domain-less** private pool (`private_api_user_pool_id`) and confirm it succeeds over the interface endpoint:
   ```bash
   aws cognito-idp describe-user-pool \
     --user-pool-id "$(terraform output -raw private_api_user_pool_id)"
   ```
3. Contrast: Attempting to call user-pool operations through the VPC endpoint against `public_edge_user_pool_id` (which has a domain) will fail because user pools with domains are incompatible with PrivateLink.

### 5. Cognito Identity Pool (STS Credential Exchange)
Exchange the User Pool ID token for temporary AWS credentials scoped to `aws_iam_role.cognito_authenticated`:
```bash
IDENTITY_ID=$(aws cognito-identity get-id \
  --identity-pool-id "$(terraform output -raw identity_pool_id)" \
  --logins "cognito-idp.us-east-1.amazonaws.com/$(terraform output -raw public_edge_user_pool_id)=${ID_TOKEN}" \
  --query 'IdentityId' --output text)

aws cognito-identity get-credentials-for-identity \
  --identity-id "${IDENTITY_ID}" \
  --logins "cognito-idp.us-east-1.amazonaws.com/$(terraform output -raw public_edge_user_pool_id)=${ID_TOKEN}"
```

---

## Honest Terraform Provider Gaps (`hashicorp/aws` `v6.73.0`)

`hashicorp/aws` `v6.73.0` was released on November 11, 2026 — just before several mid-November 2026 Amazon Cognito launches. Both user pools in this lab are provisioned with `user_pool_tier = "ESSENTIALS"` so they are ready for Essentials-tier capabilities, but the following features are **not yet exposed in Terraform HCL** and must be configured via AWS CLI, SDK, Console, or CloudFormation:

1. **AWS Secrets Manager Integration for App Client Secrets (Nov 19, 2026)**
   - Stores and automatically rotates Cognito app client secrets in AWS Secrets Manager with IAM and KMS controls (available in all Regions with both services except AWS European Sovereign Cloud — Germany; standard Secrets Manager charges apply).
   - **Alternative:** Enable `PublishSecretsInAWSSecretsManager = true` via the AWS Console, CloudFormation, or an updated AWS CLI / SDK call on `CreateUserPoolClient` / `UpdateUserPoolClient` (do not supply a custom secret value at the same time).
2. **OAuth 2.0 Token Exchange — RFC 8693 (Nov 12, 2026)**
   - Exchanges a subject token for a down-scoped, audience-bound token (no refresh token; optional `act` delegation claim when an actor token is supplied) via the Token endpoint (`grant_type=urn:ietf:params:oauth:grant-type:token-exchange`) or the `GetDerivedToken` API. Requires Essentials or Plus.
   - **Alternative:** Configure token-exchange policies and call `GetDerivedToken` / the token endpoint via AWS CLI, SDK, or Console.
3. **ACR & AMR Token Claims — Custom ACR Level URIs & Target Level Requests (Nov 17, 2026)**
   - Standard ACR (4 authentication strength levels, password-only level 1 through password+TOTP level 4) and AMR claims are emitted automatically in tokens on all user pools.
   - Requesting a target authentication level (`acr_values`) and configuring custom ACR level URIs require Essentials or Plus and are configured via AWS Console / CLI / SDK.
4. **Multi-Region Replication — MRR (Expanded Nov 20, 2026)**
   - Add-on for Essentials or Plus requiring a **multi-Region AWS KMS customer managed key (CMK)**.
   - Previously available in 16 commercial Regions + AWS GovCloud (US); expanded on Nov 20, 2026 to 16 additional commercial Regions: Asia Pacific (Hyderabad, Hong Kong, Jakarta, Malaysia, Melbourne, New Zealand, Osaka, Taipei, Thailand), Canada West (Calgary), Europe (Milan, Spain, Zurich), Israel (Tel Aviv), Mexico (Central), and Africa (Cape Town).
   - **Alternative:** Configure secondary Region replication via AWS Console, AWS CLI, or CloudFormation.
5. **Client ID Metadata Documents — CIMD Policies (Nov 19, 2026)**
   - Allows MCP clients and AI agents to identify themselves with an HTTPS URL metadata document mapped to an existing app client (Essentials or Plus).
   - **Alternative:** Configure CIMD policies via AWS Console, AWS CLI, or SDK.

---

## Cost Warnings

Running `terraform apply` creates billable AWS resources that incur **hourly and per-request charges** even while idle:

- **NAT Gateway:** Hourly charge plus per-GB data processing (~$0.045/hr in `us-east-1`).
- **Application Load Balancer:** Hourly charge plus LCU usage (~$0.0225/hr in `us-east-1`).
- **Interface VPC Endpoints (PrivateLink):** 2 endpoints (`cognito-idp`, `cognito-identity`) × 2 AZs = 4 ENI-hours (~$0.01/ENI-hr = ~$0.04/hr total) plus per-GB data processing.
- **AWS WAFv2:** Monthly Web ACL fee ($5/month prorated hourly) + rule fees ($1/rule/month prorated) + per-million request charges.
- **Amazon Cognito:** Essentials tier MAU pricing above the free tier.
- **API Gateway:** Per-million REST API requests.
- **AWS Secrets Manager (if enabled manually):** $0.40/secret/month plus API call charges.

---

## Cleanup

Destroy all resources immediately after you finish testing so hourly charges stop:

```bash
terraform destroy
```
