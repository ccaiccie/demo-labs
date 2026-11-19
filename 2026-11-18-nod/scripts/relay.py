"""Tiny TCP relay with an optional source-IP allow list (runs on the Docker host, here MYDELL2).

Usage (Windows or Linux, Python 3.8+):
    python relay.py <listen_host> <listen_port> <target_host> <target_port> [allowed_ip1,allowed_ip2]

Lab example: listen on the host's Tailscale address, forward to the Nod server that only binds 127.0.0.1:
    python relay.py <docker-host-tailscale-ip> 8095 127.0.0.1 4310 <client-tailscale-ip>

Connections from any address that is not in the allow list are closed immediately.
"""
import asyncio, sys

LH, LP, TH, TP = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
ALLOW = set(sys.argv[5].split(',')) if len(sys.argv) > 5 else None


async def pipe(r, w):
    try:
        while True:
            d = await r.read(65536)
            if not d:
                break
            w.write(d)
            await w.drain()
    except Exception:
        pass
    finally:
        try:
            w.close()
        except Exception:
            pass


async def handle(cr, cw):
    peer = cw.get_extra_info('peername')[0]
    if ALLOW and peer not in ALLOW:
        cw.close()
        return
    try:
        tr, tw = await asyncio.open_connection(TH, TP)
    except Exception:
        cw.close()
        return
    await asyncio.gather(pipe(cr, tw), pipe(tr, cw))


async def main():
    s = await asyncio.start_server(handle, LH, LP)
    async with s:
        await s.serve_forever()

asyncio.run(main())
