#!/bin/sh
# Start the clawd-connector server on 8080 in the background.
cd "$(dirname "$0")"
pkill -f 'server.py' 2>/dev/null
nohup python3 server.py > server.log 2>&1 &
echo "started, pid $!"
sleep 2
curl -s http://localhost:8080/healthz; echo
