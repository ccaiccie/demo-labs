# WEB1 - DMZ web server behind FTD1, published as 198.51.100.110
ip address add dev eth0 10.1.50.10/24
ip link set dev eth0 up
ip route replace default via 10.1.50.1
echo "<h1>WEB1 in the FTD1 DMZ (10.1.50.10)</h1>" > /usr/share/nginx/html/index.html
# keep the next line to indicate that the machine is ready
echo "READY" >/dev/console
exit 0
