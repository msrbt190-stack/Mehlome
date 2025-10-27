from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime

app = Flask(__name__)

# إعداد اللوق
logging.basicConfig(filename='sim_server.log', level=logging.INFO, format='%(message)s')

# تحميل إعدادات السيرفر
with open("server_info.json") as f:
    cfg = json.load(f)
ALLOWED_TOKENS = cfg.get("allowed_tokens", [])

def log_event(event):
    logging.info(json.dumps(event, ensure_ascii=False))
    print(json.dumps(event, ensure_ascii=False))

@app.route('/simulate', methods=['POST'])
def simulate():
    token = request.headers.get("X-Sim-Token")
    if ALLOWED_TOKENS and token not in ALLOWED_TOKENS:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    cmd = data.get("cmd")
    params = data.get("params", {})
    requester = params.get("_requested_by")

    # سجل استقبال الطلب
    log_event({
        "event": "request_received",
        "ts": int(datetime.now().timestamp()),
        "cmd": cmd,
        "params": params,
        "_requested_by": requester
    })

    # محاكاة الرد
    simulated_response = {
        "event": "simulated_response",
        "ts": int(datetime.now().timestamp()),
        "simulated": {
            "attack_id": int(datetime.now().timestamp()*1000),
            "concurrents_used": 1,
            "duration": str(params.get("duration", "0")),
            "error": False,
            "len": "1",
            "method_used": params.get("method_used", "udp"),
            "port": str(params.get("port", "")),
            "target": params.get("target", ""),
            "threads": "5",
            "time_to_send": "0ms",
            "your_running_attacks": "0/4"
        }
    }

    log_event(simulated_response)
    return jsonify({"status": "queued", "simulated": simulated_response})

if __name__ == "__main__":
    app.run(host=cfg.get("server_host", "127.0.0.1"), port=cfg.get("server_port", 8080))
