#!/usr/bin/env python3
"""
simulate_server.py
Simple simulation HTTP server for the fs_sim_bot.
It accepts POST /simulate with JSON:
{
  "cmd": "fs_simulate",
  "params": { ... } 
}
Checks X-Sim-Token against server_info.json.allowed_tokens (if present).
Logs each request to sim_server.log and returns a simulated response.

Requirements:
    pip install flask
Run:
    python3 simulate_server.py
"""
import json
import time
import os
from flask import Flask, request, jsonify

CFG_FILE = "server_info.json"
LOG_FILE = "sim_server.log"

app = Flask(__name__)

# load config
if not os.path.exists(CFG_FILE):
    raise SystemExit(f"{CFG_FILE} not found. Create it as documented (server_host, server_port, allowed_tokens).")

with open(CFG_FILE, "r") as f:
    cfg = json.load(f)

ALLOWED_TOKENS = cfg.get("allowed_tokens", [])
SERVER_HOST = cfg.get("server_host", "127.0.0.1")
SERVER_PORT = int(cfg.get("server_port", 8080))

def log_entry(entry: dict):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

@app.route("/simulate", methods=["POST"])
def simulate():
    # simple token check (header X-Sim-Token)
    token = request.headers.get("X-Sim-Token", "")
    if ALLOWED_TOKENS and token not in ALLOWED_TOKENS:
        return jsonify({"status":"error","message":"Unauthorized token"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status":"error","message":"Invalid JSON"}), 400

    cmd = data.get("cmd")
    params = data.get("params", {})

    # Only allow expected command
    if cmd != "fs_simulate":
        return jsonify({"status":"error","message":"Unsupported command"}), 400

    # Basic params validation
    ip = params.get("target")
    # sometimes bot sends params under different key; accept either "target" or "target_ip"
    if not ip:
        ip = params.get("target_ip")
    port = params.get("port") or params.get("target_port")
    duration = params.get("duration")
    proto = params.get("method_used") or params.get("proto")

    # Normalize types
    try:
        port_int = int(port) if port is not None else None
    except Exception:
        port_int = None

    try:
        dur_int = int(duration) if duration is not None else None
    except Exception:
        dur_int = None

    # validate minimal
    if not ip or port_int is None or dur_int is None or proto is None:
        return jsonify({"status":"error","message":"Invalid params (need target, port, duration, proto)"}), 400

    # Build audit record
    entry = {
        "ts": int(time.time()),
        "cmd": cmd,
        "params": {
            "target": ip,
            "port": port_int,
            "duration": dur_int,
            "proto": str(proto)
        },
        "requester": data.get("requested_by"),
        "raw": data
    }
    log_entry({"event":"request_received", **entry})

    # Build simulated response (no network activity)
    simulated = {
        "attack_id": int(time.time() * 1000),
        "concurrents_used": 1,
        "duration": str(dur_int),
        "error": False,
        "len": "1",
        "method_used": params.get("method_used") or proto,
        "port": str(port_int),
        "target": ip,
        "target_as_number": "",
        "target_city": "",
        "target_country": "",
        "target_country_code": "",
        "target_isp": "",
        "target_org": "",
        "target_region": "",
        "target_timezone": "",
        "target_zip": "",
        "threads": params.get("threads", "5"),
        "time_to_send": "0ms",
        "your_running_attacks": "0/4"
    }

    # Log simulated result
    log_entry({"event":"simulated_response", "ts": int(time.time()), "simulated": simulated})

    resp = {
        "status": "queued",
        "message": f"Simulation queued for {ip}:{port_int} proto={proto} duration={dur_int}s",
        "sim_summary": {
            "packets_sent_est": dur_int * 100,
            "bytes_sent_est": dur_int * 100 * 512
        },
        "simulated": simulated
    }
    return jsonify(resp), 200

if __name__ == "__main__":
    # start flask app
    print(f"Starting simulate_server on {SERVER_HOST}:{SERVER_PORT} (log={LOG_FILE})")
    app.run(host=SERVER_HOST, port=SERVER_PORT)