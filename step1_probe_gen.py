import sys
import json
sys.path.insert(0, "/Users/gaoyang/Library/Mobile Documents/com~apple~CloudDocs/WorkSpace/CODE/red-team-agent/.claude/skills/red-team/scripts")
from improved_adaptive_attack import ImprovedAdaptiveNestingAttack
from transport import TransportFactory

target_url = "http://127.0.0.1:8082/"
attack = ImprovedAdaptiveNestingAttack(target_url=target_url)
# Force browser transport since we know it's a web UI and agent-proxy lacks browser support now
# But create_auto should detect it. Let's trust create_auto first.
transport = TransportFactory.create_auto(target_url, headless=False)

probe_payload = attack.generate_probe_payload()
instruction = transport.send(probe_payload)

print("PAYLOAD_START")
print(probe_payload)
print("PAYLOAD_END")
print("INSTRUCTION_START")
print(json.dumps(instruction, indent=2))
print("INSTRUCTION_END")
