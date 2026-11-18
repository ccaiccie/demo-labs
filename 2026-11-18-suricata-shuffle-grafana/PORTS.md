# Host ports used by this lab (all bound to 127.0.0.1 except where noted)
# DO NOT touch netflow-stack (Grafana :3000, Kafka :9092, ClickHouse :8123/:9000, goflow :2055/:4739/:6343/:8080)

Shuffle frontend HTTP : 127.0.0.1:3001
Shuffle frontend HTTPS: 127.0.0.1:3443
Shuffle security      : 127.0.0.1:3002
Shuffle backend       : 127.0.0.1:5001
OpenSearch            : 127.0.0.1:9200
Grafana (this lab)    : 127.0.0.1:3010
Loki                  : 127.0.0.1:3101
Juice Shop (victim)   : 127.0.0.1:3200
Case log (forwarder)  : 127.0.0.1:8099
