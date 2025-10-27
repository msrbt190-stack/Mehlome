#!/usr/bin/env python3
"""
simulate_server.py
Full simulation HTTP server for fs_sim_bot (complete file).
- Accepts POST /simulate with JSON payload sent by bot.
- Performs robust parsing/normalization of fields (accepts multiple key names).
- Checks X-Sim-Token against server_info.json.allowed_tokens (if present).
- Logs received requests and simulated responses to sim_server.log.
- DOES NOT send any real network traffic to target IPs — simulation only.

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

# Load config
if not os.path.exists(CFG_FILE):
    raise SystemExit(f"{CFG_FILE} not found. Create it with server_host, server_port, allowed_tokens.")

with open(CFG_FILE, "r", encoding="utf-8") as f:
    cfg = json.load(f)

ALLOWED_TOKENS = cfg.get("allowed_tokens", [])
SERVER_HOST = cfg.get("server_host", "127.0.0.1")
SERVER_PORT = int(cfg.get("server_port", 8080))


def log_entry(entry: dict):
    """Append a JSON line to the log file (non-blocking best-effort)."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # swallow logging errors to avoid crashing the server
        pass


@app.route("/simulate", methods=["POST"])
def simulate():
    # simple token check (header X-Sim-Token)
    token = request.headers.get("X-Sim-Token", "")
    if ALLOWED_TOKENS and token not in ALLOWED_TOKENS:
        return jsonify({"status": "error", "message": "Unauthorized token"}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    # Accept command key variations
    cmd = data.get("cmd") or data.get("command")
    params = data.get("params") or {}

    # Only accept expected command
    if cmd != "fs_simulate" and cmd != "fs-simulate" and cmd != "fs_sim":
        return jsonify({"status": "error", "message": "Unsupported command"}), 400

    # Robust normalization: accept multiple possible key names
    # target can be "target" or "target_ip"
    ip = (
        params.get("target")
        or params.get("target_ip")
        or params.get("ip")
        or data.get("target")
        or data.get("target_ip")
        or None
    )

    # port can be "port", "target_port" and may be string or int
    port_raw = (
        params.get("port")
        or params.get("target_port")
        or params.get("targetPort")
        or data.get("port")
        or None
    )

    # duration may be "duration" or nested string
    duration_raw = params.get("duration") or data.get("duration") or None

    # proto can be "method_used", "proto", "protocol", or params.method
    proto = (
        params.get("method_used")
        or params.get("proto")
        or params.get("protocol")
        or params.get("method")
        or data.get("method_used")
        or data.get("proto")
        or data.get("protocol")
        or None
    )

    # Some bots may place requester at root or under params as "_requested_by" or "requested_by"
    requester = (
        data.get("requested_by")
        or data.get("requester")
        or params.get("_requested_by")
        or params.get("requested_by")
        or params.get("requester")
        or None
    )

    # Try to coerce types
    try:
        port_int = int(port_raw) if port_raw is not None else None
    except Exception:
        port_int = None

    try:
        dur_int = int(duration_raw) if duration_raw is not None else None
    except Exception:
        dur_int = None

    # Basic validation
    if not ip or port_int is None or dur_int is None or not proto:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Invalid params (need target/ip, port, duration, proto/method)",
                }
            ),
            400,
        )

    # Normalize proto to uppercase string for response
    proto_norm = str(proto).upper()

    # Build audit record
    entry = {
        "event": "request_received",
        "ts": int(time.time()),
        "cmd": "fs_simulate",
        "params": {"target": ip, "port": port_int, "duration": dur_int, "proto": proto_norm},
        "requester": requester,
        "raw": data,
    }
    log_entry(entry)

    # Build simulated result (no network activity)
    attack_id = int(time.time() * 1000)
    simulated = {
        "attack_id": attack_id,
        "concurrents_used": 1,
        "duration": str(dur_int),
        "error": False,
        "len": "1",
        "method_used": proto_norm.lower(),  # keep method lowercase like example
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
        "your_running_attacks": "0/4",
    }

    # Log simulated response
    log_entry({"event": "simulated_response", "ts": int(time.time()), "simulated": simulated})

    resp = {
        "status": "queued",
        "message": f"Simulation queued for {ip}:{port_int} proto={proto_norm} duration={dur_int}s",
        "sim_summary": {"packets_sent_est": dur_int * 100, "bytes_sent_est": dur_int * 100 * 512},
        "simulated": simulated,
    }
    return jsonify(resp), 200


if __name__ == "__main__":
    print(f"Starting simulate_server on {SERVER_HOST}:{SERVER_PORT} (log={LOG_FILE})")
    # When running in environments that already have a process on the port,
    # the app.run call will fail with Address already in use.
    app.run(host=SERVER_HOST, port=SERVER_PORT)
