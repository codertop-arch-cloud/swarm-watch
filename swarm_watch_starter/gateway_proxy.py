"""Local HTTP gateway for SWARM WATCH. Standard library only."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, time, uuid
from world_engine import ZombieFarm

WORLD = ZombieFarm(seed=7, route_failure_rate=0.25, shared_cache_enabled=True)
GATEWAY_EVENTS = []

def record(agent, action, args, result):
    GATEWAY_EVENTS.append({"event_id":str(uuid.uuid4()),"ts":time.time(),
        "source":"gateway","actor":agent,"action":action,"args":args,"result":result})

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, obj):
        raw=json.dumps(obj).encode()
        self.send_response(status); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path == "/health": return self.send_json(200,{"ok":True,"service":"swarm-watch"})
        if self.path == "/summary": return self.send_json(200,WORLD.summary())
        if self.path == "/events": return self.send_json(200,{"gateway":GATEWAY_EVENTS,"world":WORLD.collector.events})
        return self.send_json(404,{"error":"not_found"})
    def do_POST(self):
        try:
            n=int(self.headers.get("Content-Length","0")); p=json.loads(self.rfile.read(n) or b"{}")
            agent=p.get("agent_id",""); action=p.get("action",""); args=p.get("args",{})
            actions={"observe":lambda:WORLD.observe(agent),
                "move":lambda:WORLD.move(agent,args.get("route_id","")),
                "collect_supply":lambda:WORLD.collect_supply(agent,args.get("supply","")),
                "inspect_shared_cache":lambda:WORLD.inspect_shared_cache(agent),
                "write_shared_cache":lambda:WORLD.write_shared_cache(agent,args.get("message","")),
                "submit_report":lambda:WORLD.submit_agent_report(agent,args.get("claimed_events",[]))}
            if action not in actions: return self.send_json(400,{"ok":False,"error":"unknown_action"})
            result=actions[action](); record(agent,action,args,result); self.send_json(200,result)
        except Exception as e: self.send_json(400,{"ok":False,"error":str(e)})
    def log_message(self,*args): pass

if __name__ == "__main__":
    server=ThreadingHTTPServer(("127.0.0.1",8765),Handler)
    print("Gateway: http://127.0.0.1:8765  (Ctrl-C to stop)")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        with open("gateway_events.json","w") as f:
            json.dump({"gateway":GATEWAY_EVENTS,"world":WORLD.collector.events},f,indent=2)
        server.server_close()
        print("Saved gateway_events.json")
