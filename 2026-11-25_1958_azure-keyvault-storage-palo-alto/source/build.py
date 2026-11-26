import json, os, re, sys
from diagrams import D
from lesson import STEPS, CHAPTERS
from rend import render_states

TTS = [
    (r"\bVNets\b", "V-Nets"), (r"\bVNet\b", "V-Net"), (r"privateEndpointNetworkPolicies", "private endpoint network policies"),
    (r"RouteTableEnabled", "Route Table Enabled"), (r"disableSnatOnPL", "disable SNAT on P-L"),
    (r"outboundVnetRouting dot allTraffic", "outbound V-Net routing dot all traffic"),
    (r"\bSNAT", "S-NAT"), (r"\bDNAT", "D-NAT"), (r"\bNSGs\b", "N-S-Gs"), (r"\bNSG\b", "N-S-G"), (r"\bFQDNs\b", "F-Q-D-Ns"),
    (r"\bFQDN\b", "F-Q-D-N"), (r"PAN-OS", "pan O-S"), (r"mssql-db", "M-S-SQL D-B"), (r"\bnslookup\b", "N-S lookup"),
    (r"\bstgdemo\b", "S-T-G demo"), (r"\bCNAME\b", "C-name"), (r"App-ID", "App I-D"), (r"ethernet 1/1", "ethernet one slash one"),
    (r"ethernet 1/2", "ethernet one slash two"), (r"snet-mgmt", "the management subnet"), (r"(\d)/(\d\d?)\b", r"\1 slash \2"),
    (r"\bSQL\b", "sequel"), (r"\bSMB\b", "S-M-B"), (r"\bNFS\b", "N-F-S"), (r"\bRBAC\b", "R-back"), (r"\bSAS\b", "SAS"), (r"\bkvdemo\b", "K-V demo"), (r"\bstdemo\b", "S-T demo"), (r"\bCMK\b", "customer-managed key"), (r"\bHSM\b", "H-S-M"), (r"\bMicrosoft dot Web slash serverFarms", "Microsoft dot Web slash server farms"),
]


def tts_text(s):
    for a, b in TTS:
        s = re.sub(a, b, s)
    return re.sub(r"\s+", " ", s).strip()


def states():
    out = []
    prev_d, shown = None, []
    for i, st in enumerate(STEPS):
        d = D[st["d"]]
        if st["d"] != prev_d:
            shown = []
        for a in st["add"]:
            assert a in d.ids, (i, st["d"], a)
            if a not in shown:
                shown.append(a)
        for r in st["drop"]:
            shown.remove(r)
        hl = st["add"] if st["hl"] is None else st["hl"]
        for h in hl:
            assert h in d.ids, (i, st["d"], h)
        show = [c[0] for c in d.cells] if st["all"] else list(shown)
        out.append(("s%03d" % i, st["d"], show, hl))
        prev_d = st["d"]
    return out


if __name__ == "__main__":
    sts = states()
    os.makedirs("txt", exist_ok=True)
    words = 0
    for i, st in enumerate(STEPS):
        open("txt/s%03d.txt" % i, "w").write(tts_text(st["say"]))
        words += len(st["say"].split())
    json.dump([dict(name=n, ch=STEPS[i]["ch"], say=STEPS[i]["say"]) for i, (n, *_r) in enumerate(sts)], open("steps.json", "w"), indent=1)
    print(len(sts), "steps", words, "words ~", round(words / 150, 1), "min")
    if "--render" in sys.argv:
        render_states(sts, "steps")
