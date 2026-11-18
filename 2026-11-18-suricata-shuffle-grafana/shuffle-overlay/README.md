Export your Suricata alert triage workflow from Shuffle (Workflow → Export) and save it here as `suricata-alert-triage.json`.

Suggested flow:
1. Webhook trigger (receives Suricata alert JSON from the forwarder)
2. Set severity label (critical if severity <= 1, high if 2, else info)
3. HTTP POST to the lab case log at http://172.17.0.1:8099/case (Docker bridge gateway) as a confirmation sink
4. Optional: Shuffle Tools → repeat back / log execution details
