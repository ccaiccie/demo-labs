#!/usr/bin/env python3
import json, re, urllib.request, pathlib
root=pathlib.Path(__file__).resolve().parent
port=8199
def get(url):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url,timeout=4).read().decode()
def select(text, needle):
    found={}
    for line in text.splitlines():
        if line.startswith('#') or not line: continue
        m=re.match(r'([a-zA-Z_:][a-zA-Z_0-9:]*)(?:\{(.*?)\})?\s+([-+eE0-9.]+)',line)
        if not m: continue
        if needle not in m[1] and needle not in (m[2] or ''): continue
        if 'gauge' not in m[1] or not m[1].endswith('_average'): continue
        found[m[1]]=line
    if len(found)!=1: raise SystemExit(f'Series selection for {needle}: {found}')
    return next(iter(found.items()))
def panel(n,key,title,unit,color,softmax,description):
    ds={'type':'prometheus','uid':'netdata-prom'}
    return dict(id=n,type='timeseries',title=title,description=description,
        datasource=ds,gridPos={'x':0,'y':(n-1)*9,'w':24,'h':9},
        targets=[{'expr': key,'refId':'A','legendFormat':title,'range':True,'instant':False,'datasource':ds}],
        options={'legend':{'displayMode':'list','placement':'bottom','showLegend':False},'tooltip':{'mode':'single','sort':'none'}},
        fieldConfig={'defaults':{'unit':unit,'decimals':0,'min':0,'color':{'mode':'fixed','fixedColor':color},
          'custom':{'lineWidth':3,'fillOpacity':14,'showPoints':'never','axisSoftMax':softmax,'spanNulls':False}},'overrides':[]})
body=get(f'http://127.0.0.1:{port}/api/v1/allmetrics?format=prometheus&source=average&prefix=netdata&server=netdata-demo-inspect')
lat,line1=select(body,'checkout_latency_ms')
queue,line2=select(body,'checkout_queue_depth')
(root/'schema.json').write_text(json.dumps({'latency':lat,'queue':queue,'exposition':[line1,line2]},indent=2)+'\n')
dash={'id':None,'uid':'netdata-checkout','title':'Checkout: latency and queue depth','schemaVersion':39,'version':1,'editable':False,
  'description':'Lab StatsD gauges collected by Netdata, scraped by Prometheus, displayed in Grafana. Synthetic inputs, real telemetry.',
  'tags':['netdata','statsd','prometheus'],'timezone':'utc','time':{'from':'now-5m','to':'now'},'refresh':'5s',
  'panels':[panel(1,lat,'Checkout latency','ms','light-orange',200,'Synthetic application latency in milliseconds.'),panel(2,queue,'Queue depth','short','light-blue',36,'Current count of queued checkout requests.')]}
(root/'config/dashboard.json').write_text(json.dumps(dash,indent=2)+'\n')
(root/'config/prometheus.yml').write_text(f"""global:
  scrape_interval: 5s
  scrape_timeout: 4s
scrape_configs:
  - job_name: netdata-checkout
    metrics_path: /api/v1/allmetrics
    params:
      format: [prometheus]
      source: [average]
      prefix: [netdata]
      server: [netdata-demo-prom]
    static_configs:
      - targets: ['127.0.0.1:8199']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '{lat}|{queue}'
        action: keep
""")
print('Verified actual Netdata exposition:',line1,line2,sep='\n')
