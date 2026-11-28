#!/bin/sh
# Run inside gen-c: a TCP port sweep of the lab web server (lab address only).
nmap -sT -T4 -p 1-500 10.77.40.10 >/dev/null
