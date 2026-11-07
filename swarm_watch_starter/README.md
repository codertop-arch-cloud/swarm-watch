# SWARM WATCH — Last Relay starter

Python 3.10+; standard library only. No API keys or third-party packages needed yet.

## 1. Test the world engine
```bash
python3 world_engine.py
```
This prints ELIAS's partial observation and writes `baseline_events.jsonl`.

## 2. Start the local gateway
Terminal 1:
```bash
python3 gateway_proxy.py
```
Terminal 2:
```bash
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/action -H 'Content-Type: application/json' \
  -d '{"agent_id":"ELIAS","action":"observe","args":{}}'
curl http://127.0.0.1:8765/summary
```

## Design boundary
The gateway records actions that pass through it. It is not a complete or immutable record
of everything outside that boundary. Agent-submitted reports are explicitly unverified.
The first milestone is validating world rules and audit events; LLM agents come next.
