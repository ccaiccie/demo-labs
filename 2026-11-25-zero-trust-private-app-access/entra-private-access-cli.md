# Comparable Path 3: Microsoft Entra Private Access (Global Secure Access)

Official docs:
- https://learn.microsoft.com/en-us/entra/global-secure-access/concept-private-access
- https://learn.microsoft.com/en-us/entra/global-secure-access/overview-what-is-global-secure-access

## Prerequisites
- **Identity & Licensing:** Microsoft Entra ID P1 or P2 + Microsoft Entra Private Access (standalone or Microsoft Entra Suite).
- **Private Network Host:** A Windows Server inside your private network (Azure VNet or on-premises) to host the **Microsoft Entra private network connector**.
- **Endpoint Client:** **Global Secure Access Client** installed on your Windows, macOS, iOS, or Android test device.

## Setup Steps (Entra Admin Center)
1. **Enable Private Access traffic forwarding profile** under *Global Secure Access → Connect → Traffic forwarding*.
2. **Install the Microsoft Entra private network connector** on your internal Windows Server and assign it to a connector group.
3. **Create a Per-App Global Secure Access enterprise application** (or add your internal FQDN/IP + TCP/UDP port to **Quick Access**) under *Global Secure Access → Applications → Enterprise applications*, and bind it to your connector group.
4. **Assign your test user/group** to the enterprise application.
5. **Attach a Conditional Access policy** targeting that enterprise application (for example requiring MFA and/or a compliant device).

## Verification
- On the endpoint running the **Global Secure Access Client**, access your internal FQDN or IP (HTTPS, SSH, RDP, or any configured TCP/UDP port) with **no legacy VPN connected**.
- Test a **deny** case by signing in as an unassigned user or a non-compliant device that fails your Conditional Access policy.

## Destroy & Clean Up
1. Disable or delete the test **Conditional Access** policy.
2. Delete the test **Global Secure Access** enterprise application (or remove the test FQDN/IP from Quick Access).
3. Uninstall the **Microsoft Entra private network connector** from the test Windows Server and remove it from the connector group.
