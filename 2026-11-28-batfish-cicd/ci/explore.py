#!/usr/bin/env python3
"""Ad-hoc Batfish questions against the lab snapshot (used to diagnose a failing pipeline run).
Usage: python ci/explore.py <question> [args]
  nodes | edges | bgp | routes <prefix> | acl <dst_port> | trace <src_ip> <dst_ip> <dst_port>"""
import os, sys
import pandas as pd
from pybatfish.client.session import Session
from pybatfish.datamodel import HeaderConstraints

pd.set_option("display.width", 138); pd.set_option("display.max_columns", 12)
pd.set_option("display.max_colwidth", 60)
bf = Session(host=os.environ.get("BATFISH_HOST", "127.0.0.1"))
bf.set_network(os.environ.get("BATFISH_NETWORK", "batfish-ci-lab"))
bf.init_snapshot(os.environ.get("SNAPSHOT_DIR", "snapshots/lab"), name="explore", overwrite=True)
q, a = sys.argv[1], sys.argv[2:]
if q == "nodes":
    df = bf.q.nodeProperties(properties="Configuration_Format,Interfaces").answer().frame()
    df["Interfaces"] = df["Interfaces"].apply(lambda x: ", ".join(x))
elif q == "edges":
    df = bf.q.layer3Edges().answer().frame()
    df = df[["Interface", "IPs", "Remote_Interface", "Remote_IPs"]]
elif q == "bgp":
    df = bf.q.bgpSessionCompatibility().answer().frame()
    df = df[["Node", "Local_IP", "Local_AS", "Remote_Node", "Remote_IP", "Remote_AS", "Configured_Status"]]
elif q == "routes":
    df = bf.q.routes(network=a[0]).answer().frame()
    keep = [c for c in ["Node", "Network", "Next_Hop", "Next_Hop_IP", "Protocol", "Metric"] if c in df.columns]
    df = df[keep] if not df.empty else df
elif q == "acl":
    hc = HeaderConstraints(srcIps="192.0.2.50", dstIps="203.0.113.10", ipProtocols=["TCP"], dstPorts=a[0])
    df = bf.q.testFilters(nodes="edge-rtr", filters="EDGE_IN", headers=hc).answer().frame()
    df = df[["Node", "Filter_Name", "Flow", "Action", "Line_Content"]]
elif q == "trace":
    hc = HeaderConstraints(srcIps=a[0], dstIps=a[1], ipProtocols=["TCP"], dstPorts=a[2])
    df = bf.q.traceroute(startLocation="@enter(branch-rtr[GigabitEthernet0/0])", headers=hc).answer().frame()
    for _, r in df.iterrows():
        print("Flow:", r.Flow)
        for t in r.Traces:
            print("Disposition:", t.disposition)
            for i, h in enumerate(t.hops, 1):
                print(f"  hop {i}: {h.node}")
                for s in h.steps:
                    print("     ", str(s)[:126])
    sys.exit(0)
else:
    sys.exit(__doc__)
print(df.to_string(index=False) if not df.empty else "(no rows)")
