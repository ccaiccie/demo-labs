#!/usr/bin/env python3
import datetime,socket,sys,time
phase_map={'baseline':(25,2),'spike':(180,32),'recovery':(25,2)}
phases=sys.argv[1:]
if not phases or any(x not in phase_map for x in phases):
    raise SystemExit("Use: python3 phase.py baseline spike recovery")
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
    for p in phases:
        lat,queue=phase_map[p]
        print(f'{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")} {p}: {lat} ms, depth {queue}',flush=True)
        payload=f"lab.checkout_latency_ms:{lat}|g\nlab.checkout_queue_depth:{queue}|g".encode()
        next_send=time.monotonic()
        for _ in range(60):
            s.sendto(payload,('127.0.0.1',8125))
            next_send+=1
            time.sleep(max(0,next_send-time.monotonic()))
