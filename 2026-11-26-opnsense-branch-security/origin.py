#!/usr/bin/env python3
"""Serve deterministic, harmless test traffic on the lab origin only."""
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from urllib.parse import urlsplit

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        key={'/docs':'DOCS_OK','/uploads':'UPLOADS_OK','/health':'HEALTH_OK',
             '/ids-check':'BRANCH_LAB_IDS_MARKER_8E79'}.get(path)
        data=(key or 'NOT_FOUND').encode()+b'\n'
        self.send_response(200 if key else 404)
        self.send_header('Content-Type','text/plain')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def main():
    p=ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,choices=[80,443,8080,8443],required=True)
    p.add_argument('--bind',choices=['198.18.83.10','127.0.0.1'],default='198.18.83.10')
    p.add_argument('--cert',type=Path)
    p.add_argument('--key',type=Path)
    cfg=p.parse_args()
    if bool(cfg.cert) != bool(cfg.key):
        p.error('--cert and --key must be given together')
    with ThreadingHTTPServer((cfg.bind,cfg.port),Handler) as srv:
        if cfg.cert:
            tls=SSLContext(PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(cfg.cert,cfg.key)
            srv.socket=tls.wrap_socket(srv.socket,server_side=True)
        srv.serve_forever()

if __name__=='__main__':
    main()
