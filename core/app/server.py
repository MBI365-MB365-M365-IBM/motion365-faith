import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from registry import get_registry, put_registry

CORE_VERSION = "1.0.0"

OBJECTS = [
    "MotionIdentity",
    "MotionOrb",
    "MotionGoggle",
    "GalaxyContext",
    "MotionSkill",
    "MotionPermission",
    "MotionEvent",
    "MotionBlueprint",
    "BenchmarkResult",
    "Portal913Event",
]

def now():
    return datetime.now(timezone.utc).isoformat()

def confidence(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))

def resolve_motion(payload):
    source = payload.get("source", "unknown")
    intent = payload.get("intent")
    signals = payload.get("signals") or {}
    requested_skill = payload.get("skill")

    # Explicit intent takes precedence over inferred signals.
    if not intent:
        text = str(signals.get("text", "")).lower()

        if any(x in text for x in ["open", "go to", "navigate"]):
            intent = "navigate"
        elif any(x in text for x in ["create", "build", "make"]):
            intent = "create"
        elif any(x in text for x in ["show", "find", "inspect"]):
            intent = "inspect"
        else:
            intent = "unknown"

    # Demeanor is treated only as an uncertain interaction signal.
    demeanor = signals.get("demeanor") or {}
    urgency = confidence(demeanor.get("urgency", 0.0))

    if requested_skill:
        skill = requested_skill
    elif intent == "navigate":
        skill = "navigate"
    elif intent == "create":
        skill = "creation"
    elif intent == "inspect":
        skill = "inspection"
    else:
        skill = "clarify"

    # No direct execution permission is granted by inference.
    permission = "user"
    action = "suggest" if intent == "unknown" else "prepare"

    event = {
        "event_type": "motion.resolve",
        "timestamp": now(),
        "source": source,
        "intent": intent,
        "skill": skill,
        "permission": permission,
        "action": action,
    }

    return {
        "motion_version": CORE_VERSION,
        "intent": {
            "type": intent,
            "confidence": 0.90 if payload.get("intent") else 0.65,
        },
        "context": {
            "galaxy": payload.get("galaxy", True),
            "portal": payload.get("portal"),
            "world": payload.get("world"),
            "signals_present": sorted(signals.keys()),
        },
        "skill": {
            "id": f"M365-SKILL-{skill.upper()}",
            "name": skill,
        },
        "permission": {
            "level": permission,
            "required": True,
        },
        "execution": {
            "mode": "simulate_then_execute",
            "action": action,
        },
        "demeanor_signal": {
            "urgency": urgency,
            "used_for_response_adaptation": urgency > 0,
        },
        "event": event,
    }

class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, data):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode())

    def do_GET(self):
        if self.path == "/v1/registry":
            try:
                return self.send_json(200, get_registry())
            except Exception as exc:
                return self.send_json(500, {
                    "error": "registry_read_failed",
                    "detail": str(exc)
                })

        if self.path == "/health":
            return self.send_json(200, {
                "status": "ok",
                "service": "motion-core",
                "version": CORE_VERSION,
                "timestamp": now(),
            })

        if self.path == "/":
            return self.send_json(200, {
                "service": "motion-core",
                "version": CORE_VERSION,
                "status": "online",
                "mode": "private",
            })

        if self.path == "/v1/manifest":
            return self.send_json(200, {
                "core": "Motion Core",
                "version": CORE_VERSION,
                "objects": OBJECTS,
                "flow": [
                    "input",
                    "goggle",
                    "intent",
                    "context",
                    "skill",
                    "permission",
                    "simulate",
                    "execute",
                    "verify",
                    "benchmark",
                    "portal913",
                    "response",
                ],
            })

        self.send_json(404, {"error": "not_found"})

    def do_PUT(self):
        if self.path == "/v1/registry":
            try:
                payload = self.read_json()
                data = payload.get("registry", payload)
                return self.send_json(200, put_registry(data))
            except Exception as exc:
                return self.send_json(400, {
                    "error": "registry_write_failed",
                    "detail": str(exc)
                })

        return self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path == "/v1/motion/resolve":
            try:
                payload = self.read_json()
                result = resolve_motion(payload)
                return self.send_json(200, result)
            except Exception as exc:
                return self.send_json(400, {
                    "error": "invalid_request",
                    "detail": str(exc),
                })

        self.send_json(404, {"error": "not_found"})

    def log_message(self, fmt, *args):
        print("[motion-core]", fmt % args)

ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
