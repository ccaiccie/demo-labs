#!/usr/bin/env python3
import datetime,json,pathlib,sys,urllib.parse,urllib.request
base=pathlib.Path(__file__).resolve().parent
o=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def get(port,path,params={}):
    tail='?'+urllib.parse.urlencode(params) if params else ''
    with o.open(f'http://127.0.0.1:{port}{path}{tail}',timeout=6) as r:
        return json.load(r)
schema=json.loads((base/'schema.json').read_text())
phase_times={}
for line in (base/'phases.log').read_text().splitlines():
    stamp,phase=line.split()[:2]
    phase_times[phase.rstrip(':')]=datetime.datetime.fromisoformat(stamp).timestamp()
proof={'targets':get(9090,'/api/v1/targets')['data']['activeTargets'],'grafana':get(3090,'/api/health'),'checks':{}}
assert any(x['health']=='up' and x['labels'].get('job')=='netdata-checkout' for x in proof['targets']),proof['targets']
assert get(3090,'/api/dashboards/uid/netdata-checkout')['dashboard']['uid']=='netdata-checkout'
for phase,v in {'baseline':(25,2),'spike':(180,32),'recovery':(25,2)}.items():
    t=round(phase_times[phase]+25)
    samples={}
    for key,want in zip(('latency','queue'),v):
        p=get(9090,'/api/v1/query',{'query':schema[key],'time':t})
        series=p['data']['result']
        assert len(series)==1,(phase,key,p)
        n=float(series[0]['value'][1]); assert abs(n-want)<0.1,(phase,key,n,want)
        samples[key]=series[0]
    proof['checks'][phase]={'utc':datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat(),'samples':samples}
(base/'verification.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Prometheus target UP. Provisioned Grafana dashboard present.')
for phase,check in proof['checks'].items():
    print(check['utc'],phase,*(x['value'][1] for x in check['samples'].values()))
