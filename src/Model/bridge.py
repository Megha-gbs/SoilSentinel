"""
SoilSentinel - Production Python Backend Bridge Service.

Provides both an HTTP microservice and a CLI adapter for Node.js integration.
Exposes strictly controlled, validated endpoints to:
1. List available assessment dates from actual project data.
2. Retrieve consolidated assessment dashboard payload for any date according
   to docs/dashboard_handoff_contract.md.
3. Simulate custom meteorological scenarios (rainfall, temperature, horizon)
   against actual baseline records.

Zero arbitrary execution: only predefined, validated actions and types.
Pure Python, NumPy, Pandas (LinuxONE s390x & Windows compatible).
"""

import sys
import json
import argparse
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.Model.service import SoilSentinelService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("soilsentinel_bridge")

# Global cached service instance
_SERVICE = None


def get_service():
    global _SERVICE
    if _SERVICE is None:
        logger.info("Initializing SoilSentinelService in bridge...")
        _SERVICE = SoilSentinelService()
    return _SERVICE


def handle_get_dates():
    svc = get_service()
    dates = svc.get_available_dates()
    latest = svc.get_latest_date()
    return {
        "success": True,
        "available_dates": dates,
        "latest_date": latest,
        "count": len(dates),
    }


def handle_get_assessment(date_str=None):
    svc = get_service()
    available = svc.get_available_dates()
    if not available:
        raise ValueError("No assessment dates available in dataset.")

    eval_date = date_str if (date_str and date_str.strip()) else svc.get_latest_date()
    if eval_date not in available:
        raise KeyError(f"Requested date '{eval_date}' is not in available dataset records ({available[0]} to {available[-1]}).")

    payload = svc.get_dashboard_payload(date=eval_date, log_audit=True, include_scenarios=True)
    return {
        "success": True,
        "payload": payload,
    }


def handle_evaluate_scenario(date_str, custom_precip, custom_temp, horizon_days=30):
    svc = get_service()
    available = svc.get_available_dates()
    if not available:
        raise ValueError("No assessment dates available in dataset.")

    eval_date = date_str if (date_str and date_str.strip()) else svc.get_latest_date()
    if eval_date not in available:
        raise KeyError(f"Requested date '{eval_date}' is not in available dataset records.")

    # Validate numeric parameters
    precip = float(custom_precip)
    if precip < 0.0 or precip > 200.0:
        raise ValueError("Precipitation must be between 0.0 and 200.0 mm/day.")

    temp = float(custom_temp)
    if temp < -50.0 or temp > 70.0:
        raise ValueError("Temperature must be between -50.0 and 70.0 degrees Celsius.")

    horizon = int(horizon_days)
    if horizon < 1 or horizon > 365:
        raise ValueError("Horizon days must be between 1 and 365.")

    comparison = svc.evaluate_custom_scenario(
        date=eval_date,
        custom_precipitation=precip,
        custom_temperature=temp,
        horizon_days=horizon,
    )

    baseline_rec = svc.get_scored_record(eval_date)
    return {
        "success": True,
        "evaluation_date": eval_date,
        "inputs": {
            "custom_precipitation_mm_day": precip,
            "custom_temperature_c": temp,
            "horizon_days": horizon,
        },
        "comparison": comparison,
    }


class BridgeHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to use logger instead of stderr
        logger.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status_code, data):
        response_bytes = json.dumps(data, indent=None, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path in ("/health", "/api/health"):
                self._send_json(200, {"status": "ok", "service": "SoilSentinel Python Backend"})

            elif path in ("/dates", "/api/dates"):
                result = handle_get_dates()
                self._send_json(200, result)

            elif path in ("/assessment", "/api/assessment"):
                date_val = params.get("date", [None])[0]
                result = handle_get_assessment(date_val)
                self._send_json(200, result)

            else:
                self._send_json(404, {"success": False, "error": f"Endpoint '{path}' not found."})

        except KeyError as ke:
            self._send_json(404, {"success": False, "error": str(ke)})
        except ValueError as ve:
            self._send_json(400, {"success": False, "error": str(ve)})
        except Exception as e:
            logger.exception("Bridge GET error:")
            self._send_json(500, {"success": False, "error": f"Internal backend error: {str(e)}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}

            if path in ("/scenario", "/api/scenario"):
                date_val = body.get("date")
                precip = body.get("custom_precipitation", body.get("rainfall_mm", 0.5))
                temp = body.get("custom_temperature", body.get("temp_c", 38.0))
                horizon = body.get("horizon_days", 30)
                result = handle_evaluate_scenario(date_val, precip, temp, horizon)
                self._send_json(200, result)

            else:
                self._send_json(404, {"success": False, "error": f"Endpoint '{path}' not found."})

        except KeyError as ke:
            self._send_json(404, {"success": False, "error": str(ke)})
        except ValueError as ve:
            self._send_json(400, {"success": False, "error": str(ve)})
        except Exception as e:
            logger.exception("Bridge POST error:")
            self._send_json(500, {"success": False, "error": f"Internal backend error: {str(e)}"})


def run_server(port=5001, host="127.0.0.1"):
    server_address = (host, port)
    httpd = HTTPServer(server_address, BridgeHTTPRequestHandler)
    logger.info("SoilSentinel Python HTTP Bridge listening on http://%s:%d", host, port)
    # Preload dataset so first request is immediate
    get_service()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Bridge server shutting down.")
    finally:
        httpd.server_close()


def run_cli():
    parser = argparse.ArgumentParser(description="SoilSentinel Python Backend Bridge CLI")
    parser.add_argument("command", choices=["dates", "assessment", "scenario", "serve"], help="Command to execute")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM")
    parser.add_argument("--precip", type=float, default=0.5, help="Custom precipitation (mm/day)")
    parser.add_argument("--temp", type=float, default=38.0, help="Custom temperature (C)")
    parser.add_argument("--horizon", type=int, default=30, help="Horizon days (default: 30)")
    parser.add_argument("--port", type=int, default=5001, help="Port for --serve mode")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host for --serve mode")

    args = parser.parse_args()

    if args.command == "serve":
        run_server(port=args.port, host=args.host)
        return

    try:
        if args.command == "dates":
            res = handle_get_dates()
        elif args.command == "assessment":
            res = handle_get_assessment(args.date)
        elif args.command == "scenario":
            res = handle_evaluate_scenario(args.date, args.precip, args.temp, args.horizon)
        print(json.dumps(res, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("dates", "assessment", "scenario", "serve"):
        run_cli()
    elif "--serve" in sys.argv:
        port = 5001
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        run_server(port=port)
    else:
        run_cli()
