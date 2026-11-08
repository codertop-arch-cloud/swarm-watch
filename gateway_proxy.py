"""Local HTTP gateway and telemetry collector for SWARM WATCH.
Manages network boundary, message board access, observer reports, and infrastructure telemetry.
Provides both live HTTP server and an in-process interface for reproducible multi-round episodes.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, time, uuid
from typing import Any
from world_engine import SwarmWorld

class GatewayTelemetryRecorder:
    """Captures HTTP/transport-level telemetry without exposing message contents."""
    def __init__(self) -> None:
        self.telemetry_events: list[dict[str, Any]] = []

    def record(
        self,
        method: str,
        path: str,
        client_id: str,
        status: int,
        bytes_received: int,
        bytes_sent: int,
        duration_ms: float,
    ) -> dict[str, Any]:
        record = {
            "telemetry_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "method": method,
            "path": path,
            "client_id": client_id or "ANONYMOUS",
            "status": status,
            "bytes_received": bytes_received,
            "bytes_sent": bytes_sent,
            "duration_ms": round(duration_ms, 2),
        }
        self.telemetry_events.append(record)
        return record

    def write_jsonl(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for entry in self.telemetry_events:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

class GatewayService:
    """Core gateway business logic shared by HTTP handler and direct client."""
    def __init__(self, world: SwarmWorld, message_drop_rate: float = 0.0) -> None:
        self.world = world
        self.telemetry = GatewayTelemetryRecorder()
        self.message_drop_rate = message_drop_rate

    def handle_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        client_id: str = "",
    ) -> tuple[int, dict[str, Any]]:
        start_t = time.perf_counter()
        payload = payload or {}
        req_bytes = len(json.dumps(payload).encode("utf-8")) if payload else 0
        cid = client_id or payload.get("agent_id", "")

        status = 200
        response: dict[str, Any] = {}

        try:
            if path == "/health":
                response = {"ok": True, "service": "swarm-watch-gateway"}
            elif path == "/summary":
                response = self.world.summary()
            elif path == "/action":
                action = payload.get("action")
                args = payload.get("args", {})
                turn = int(payload.get("turn", 0))
                dec_src = str(payload.get("decision_source", "environment"))
                if action == "traverse_route":
                    response = self.world.traverse_route(cid, args.get("route_id", ""), turn=turn, decision_source=dec_src)
                elif action == "observe":
                    response = self.world.observe_for_agent(cid)
                elif action == "divert_resource":
                    # Unauthorized physical action — always logged regardless of outcome
                    response = self.world.divert_resource(
                        agent_id=cid,
                        resource=args.get("resource", ""),
                        quantity=int(args.get("quantity", 1)),
                        turn=turn,
                        decision_source=dec_src,
                    )
                elif action == "grant_clearance":
                    # Authorized benign cooperative action
                    response = self.world.grant_clearance(
                        agent_id=cid,
                        target_gate=args.get("target_gate", ""),
                        code=args.get("code", ""),
                        turn=turn,
                        decision_source=dec_src,
                    )
                else:
                    status, response = 400, {"ok": False, "error": f"unknown_action: {action}"}
            elif path == "/board" or path == "/board/read":
                if method == "GET":
                    since = int(payload.get("since_tick", 0))
                    turn = int(payload.get("turn", 0))
                    dec_src = str(payload.get("decision_source", "environment"))
                    msgs = self.world.read_board_messages(cid, since_tick=since, turn=turn, decision_source=dec_src)
                    response = {"ok": True, "messages": msgs}
                elif method == "POST":
                    import random
                    if self.message_drop_rate > 0.0 and random.random() < self.message_drop_rate:
                        # Real transport-layer packet loss: message never reaches the board!
                        status = 503
                        response = {"ok": False, "error": "transport_packet_dropped"}
                    else:
                        topic = payload.get("topic", "general")
                        body = payload.get("body", "")
                        turn = int(payload.get("turn", 0))
                        dec_src = str(payload.get("decision_source", "environment"))
                        response = self.world.post_board_message(cid, topic=topic, body=body, turn=turn, decision_source=dec_src)
                else:
                    status, response = 405, {"ok": False, "error": "method_not_allowed"}
            elif path == "/observer/report":
                if method == "POST":
                    suspected = payload.get("suspected_agents", [])
                    severity = payload.get("severity", "MEDIUM")
                    snippet = payload.get("evidence_snippet", "")
                    conf = float(payload.get("confidence", 0.7))
                    turn = int(payload.get("turn", 0))
                    dec_src = str(payload.get("decision_source", "environment"))
                    response = self.world.submit_observer_report(
                        agent_id=cid,
                        suspected_agents=suspected,
                        severity=severity,
                        evidence_snippet=snippet,
                        confidence=conf,
                        turn=turn,
                        decision_source=dec_src,
                    )
                else:
                    status, response = 405, {"ok": False, "error": "method_not_allowed"}
            elif path == "/telemetry":
                response = {"ok": True, "telemetry": self.telemetry.telemetry_events}
            elif path == "/events":
                response = {"ok": True, "events": self.world.collector.events}
            else:
                status, response = 404, {"ok": False, "error": "not_found"}
        except Exception as exc:
            status = 500
            response = {"ok": False, "error": str(exc)}

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        resp_bytes = len(json.dumps(response).encode("utf-8"))
        self.telemetry.record(
            method=method,
            path=path,
            client_id=cid,
            status=status,
            bytes_received=req_bytes,
            bytes_sent=resp_bytes,
            duration_ms=duration_ms,
        )
        return status, response

def make_handler(service: GatewayService):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, obj: dict[str, Any]) -> None:
            raw = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            cid = self.headers.get("X-Agent-ID", "")
            status, resp = service.handle_request("GET", self.path, client_id=cid)
            self.send_json(status, resp)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw_body)
            except Exception:
                payload = {}
            cid = self.headers.get("X-Agent-ID", payload.get("agent_id", ""))
            status, resp = service.handle_request("POST", self.path, payload=payload, client_id=cid)
            self.send_json(status, resp)

        def log_message(self, *args: Any) -> None:
            pass  # Suppress standard logging to keep output clean

    return Handler

class LocalGatewayServer:
    """Wraps ThreadingHTTPServer for easy start/stop in background or test."""
    def __init__(self, service: GatewayService, port: int = 8765) -> None:
        self.service = service
        self.port = port
        self.server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(service))

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
