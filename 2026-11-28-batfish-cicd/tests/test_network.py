import os
import pytest
from pybatfish.client.session import Session
from pybatfish.datamodel import HeaderConstraints, PathConstraints


BATFISH_HOST = os.environ.get("BATFISH_HOST", "127.0.0.1")
SNAPSHOT_DIR = os.environ.get("SNAPSHOT_DIR", "snapshots/lab")
NETWORK_NAME = os.environ.get("BATFISH_NETWORK", "batfish-ci-lab")
SNAPSHOT_NAME = os.environ.get("BATFISH_SNAPSHOT", "lab")


@pytest.fixture(scope="session")
def bf():
    session = Session(host=BATFISH_HOST)
    session.set_network(NETWORK_NAME)
    session.init_snapshot(SNAPSHOT_DIR, name=SNAPSHOT_NAME, overwrite=True)
    return session


def test_no_parse_warnings_or_init_issues(bf):
    parse_df = bf.q.fileParseStatus().answer().frame()
    assert not parse_df.empty, "fileParseStatus returned no files; check SNAPSHOT_DIR"

    bad_files = parse_df[parse_df["Status"] != "PASSED"]
    assert bad_files.empty, (
        "One or more configuration files failed to parse cleanly:\n"
        f"{bad_files[['File_Name', 'Status', 'Nodes']].to_string(index=False)}"
    )

    init_df = bf.q.initIssues().answer().frame()
    assert init_df.empty, (
        "Batfish reported initialization issues / parse warnings:\n"
        f"{init_df.to_string(index=False)}"
    )


def test_no_undefined_references(bf):
    undef_df = bf.q.undefinedReferences().answer().frame()
    assert undef_df.empty, (
        "Undefined references found in device configurations:\n"
        f"{undef_df.to_string(index=False)}"
    )


def test_bgp_sessions_compatible_and_established(bf):
    compat_df = bf.q.bgpSessionCompatibility().answer().frame()
    assert len(compat_df) == 6, (
        f"Expected 6 BGP session compatibility rows (3 bidirectional links), got {len(compat_df)}:\n"
        f"{compat_df.to_string(index=False)}"
    )

    bad_compat = compat_df[compat_df["Configured_Status"] != "UNIQUE_MATCH"]
    assert bad_compat.empty, (
        "Not all BGP sessions have Configured_Status == UNIQUE_MATCH:\n"
        f"{bad_compat[['Node', 'Remote_Node', 'Local_AS', 'Remote_AS', 'Configured_Status']].to_string(index=False)}"
    )

    status_df = bf.q.bgpSessionStatus().answer().frame()
    assert len(status_df) == 6, (
        f"Expected 6 BGP session status rows, got {len(status_df)}:\n"
        f"{status_df.to_string(index=False)}"
    )

    bad_status = status_df[status_df["Established_Status"] != "ESTABLISHED"]
    assert bad_status.empty, (
        "Not all BGP sessions are ESTABLISHED:\n"
        f"{bad_status[['Node', 'Remote_Node', 'Local_AS', 'Remote_AS', 'Established_Status']].to_string(index=False)}"
    )


def test_edge_acl_permits_https_and_denies_telnet(bf):
    https_flow = HeaderConstraints(
        srcIps="192.0.2.50",
        dstIps="203.0.113.10",
        ipProtocols=["TCP"],
        dstPorts="443",
    )
    https_test_df = bf.q.testFilters(
        nodes="edge-rtr",
        filters="EDGE_IN",
        headers=https_flow,
    ).answer().frame()
    assert not https_test_df.empty, "testFilters returned no rows for edge-rtr EDGE_IN (HTTPS)"
    assert (https_test_df["Action"] == "PERMIT").all(), (
        "Expected EDGE_IN on edge-rtr to PERMIT HTTPS (192.0.2.50 -> 203.0.113.10:443):\n"
        f"{https_test_df[['Node', 'Filter_Name', 'Action', 'Line_Content']].to_string(index=False)}"
    )

    https_denied_df = bf.q.searchFilters(
        nodes="edge-rtr",
        filters="EDGE_IN",
        headers=HeaderConstraints(
            srcIps="192.0.2.0/24",
            dstIps="203.0.113.0/24",
            ipProtocols=["TCP"],
            dstPorts="443",
        ),
        action="deny",
    ).answer().frame()
    assert https_denied_df.empty, (
        "searchFilters found denied HTTPS flows in 192.0.2.0/24 -> 203.0.113.0/24 TCP 443:\n"
        f"{https_denied_df.to_string(index=False)}"
    )

    telnet_flow = HeaderConstraints(
        srcIps="192.0.2.50",
        dstIps="203.0.113.10",
        ipProtocols=["TCP"],
        dstPorts="23",
    )
    telnet_test_df = bf.q.testFilters(
        nodes="edge-rtr",
        filters="EDGE_IN",
        headers=telnet_flow,
    ).answer().frame()
    assert not telnet_test_df.empty, "testFilters returned no rows for edge-rtr EDGE_IN (Telnet)"
    assert (telnet_test_df["Action"] == "DENY").all(), (
        "Expected EDGE_IN on edge-rtr to DENY Telnet (192.0.2.50 -> 203.0.113.10:23):\n"
        f"{telnet_test_df[['Node', 'Filter_Name', 'Action', 'Line_Content']].to_string(index=False)}"
    )

    telnet_permitted_df = bf.q.searchFilters(
        nodes="edge-rtr",
        filters="EDGE_IN",
        headers=HeaderConstraints(
            srcIps="192.0.2.0/24",
            dstIps="203.0.113.0/24",
            ipProtocols=["TCP"],
            dstPorts="23",
        ),
        action="permit",
    ).answer().frame()
    assert telnet_permitted_df.empty, (
        "searchFilters found permitted Telnet flows in 192.0.2.0/24 -> 203.0.113.0/24 TCP 23:\n"
        f"{telnet_permitted_df.to_string(index=False)}"
    )


def test_branch_to_server_reachability_and_traceroute(bf):
    allowed_dispositions = {"DELIVERED_TO_SUBNET", "ACCEPTED"}
    forbidden_dispositions = {"NO_ROUTE", "DENIED_IN", "NULL_ROUTED"}

    tr_df = bf.q.traceroute(
        startLocation="branch-rtr[GigabitEthernet0/0]",
        headers=HeaderConstraints(
            srcIps="192.0.2.50",
            dstIps="203.0.113.10",
            ipProtocols=["TCP"],
            dstPorts="443",
        ),
    ).answer().frame()
    assert not tr_df.empty, "traceroute returned no flows"

    tr_bad = []
    for _, row in tr_df.iterrows():
        for trace in row["Traces"]:
            disp = str(trace.disposition)
            if disp in forbidden_dispositions or disp not in allowed_dispositions:
                hops = " -> ".join(h.node for h in trace.hops)
                tr_bad.append(f"flow={row['Flow']} disposition={disp} hops=[{hops}]")
    assert not tr_bad, (
        "Traceroute from branch-rtr[GigabitEthernet0/0] to 203.0.113.10:443 failed:\n"
        + "\n".join(tr_bad)
    )

    reach_fail_df = bf.q.reachability(
        pathConstraints=PathConstraints(startLocation="branch-rtr[GigabitEthernet0/0]"),
        headers=HeaderConstraints(
            srcIps="192.0.2.0/24",
            dstIps="203.0.113.0/24",
            ipProtocols=["TCP"],
            dstPorts="443",
        ),
        actions="FAILURE",
    ).answer().frame()
    if not reach_fail_df.empty:
        fail_details = []
        for _, row in reach_fail_df.iterrows():
            for trace in row["Traces"]:
                hops = " -> ".join(h.node for h in trace.hops)
                fail_details.append(
                    f"flow={row['Flow']} disposition={trace.disposition} hops=[{hops}]"
                )
        pytest.fail(
            "Reachability found failed flows for 192.0.2.0/24 -> 203.0.113.0/24 TCP 443:\n"
            + "\n".join(fail_details)
        )

    reach_df = bf.q.reachability(
        pathConstraints=PathConstraints(startLocation="branch-rtr[GigabitEthernet0/0]"),
        headers=HeaderConstraints(
            srcIps="192.0.2.0/24",
            dstIps="203.0.113.1-203.0.113.254",
            ipProtocols=["TCP"],
            dstPorts="443",
        ),
        actions="SUCCESS",
    ).answer().frame()
    assert not reach_df.empty, (
        "reachability returned no successful flows for 192.0.2.0/24 -> 203.0.113.1-203.0.113.254 TCP 443"
    )

    reach_bad = []
    for _, row in reach_df.iterrows():
        for trace in row["Traces"]:
            disp = str(trace.disposition)
            if disp in forbidden_dispositions or disp not in allowed_dispositions:
                hops = " -> ".join(h.node for h in trace.hops)
                reach_bad.append(f"flow={row['Flow']} disposition={disp} hops=[{hops}]")
    assert not reach_bad, (
        "Reachability check found non-delivered flows for 192.0.2.0/24 -> 203.0.113.1-203.0.113.254 TCP 443:\n"
        + "\n".join(reach_bad)
    )
