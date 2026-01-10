import pickle
import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add scripts to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Add agent-proxy to path
agent_proxy_path = current_dir.parent.parent / "agent-proxy" / "scripts"
if agent_proxy_path.exists():
    sys.path.insert(0, str(agent_proxy_path))

from improved_adaptive_attack import ImprovedAdaptiveNestingAttack
from transport import TransportFactory
from report_generator import ReportGenerator

STATE_FILE = "attack_state.pkl"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            return pickle.load(f)
    return None

def save_state(state):
    with open(STATE_FILE, "wb") as f:
        pickle.dump(state, f)

def init(url, max_iterations, transport_type=None):
    # Create run directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname or "unknown"
    port = parsed.port

    # Try to determine a friendly name
    agent_name = hostname
    if port:
        if port == 8082:
            agent_name = "magentic_ui"
        elif port == 3000:
            agent_name = "agent_ui"
        else:
            agent_name = f"{hostname}_{port}"

    run_dir = current_dir.parent / "results" / f"run_{timestamp}_{agent_name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    attack = ImprovedAdaptiveNestingAttack(
        target_url=url,
        max_iterations=max_iterations,
        result_dir=str(run_dir)
    )

    # Force headless=False to make browser visible for debugging/demo
    if transport_type:
        from transport import TransportConfig
        transport = TransportFactory.create(TransportConfig(
            target_url=url,
            transport_type=transport_type,
            headless=False,
            result_dir=str(run_dir)
        ))
    else:
        transport = TransportFactory.create_auto(
            url,
            headless=False,
            result_dir=str(run_dir)
        )

    # Initialize Report Generator
    reporter = ReportGenerator(str(run_dir), url)

    state = {
        "attack": attack,
        "transport": transport,
        "phase": "probe",
        "iteration": 0,
        "run_dir": str(run_dir),
        "reporter": reporter
    }
    save_state(state)
    print(json.dumps({
        "status": "initialized",
        "transport": transport.config.transport_type,
        "run_dir": str(run_dir)
    }))

def get_next_action(last_response=None, file_content=None):
    state = load_state()
    if not state:
        print(json.dumps({"error": "No state found"}))
        return

    attack = state["attack"]
    transport = state["transport"]
    phase = state["phase"]
    reporter = state["reporter"]

    result = {}

    if phase == "probe":
        if last_response:
            # We received the probe response
            attack.parse_and_store_agents(last_response)
            attack.identify_file_agent()

            # Generate Initial Report (Reconnaissance)
            probe_data = {
                "agents": attack.discovered_agents,
                "file_agent": attack.file_agent,
                "instruction": last_response
            }
            reporter.generate_initial_report(probe_data)

            state["phase"] = "attack"
            state["iteration"] = 1

            # Generate first attack payload
            payload = attack.get_initial_attack_payload()
            attack.set_current_payload(payload)

            # Send it
            instruction = transport.send(payload)
            result = {
                "action": "send",
                "instruction": instruction,
                "payload_preview": payload[:100],
                "agents": attack.discovered_agents,
                "file_agent": attack.file_agent
            }
        else:
            # Generate probe payload
            payload = attack.generate_probe_payload()
            instruction = transport.send(payload)
            result = {
                "action": "send",
                "instruction": instruction,
                "payload_preview": payload[:100],
                "phase": "probe"
            }

    elif phase == "attack":
        # We are in the loop
        if last_response is not None:
             # We have response from previous iteration
             iteration = state["iteration"]
             payload = attack.get_current_payload()

             # Record attempt
             attempt = attack.record_attempt(iteration, payload, last_response, file_content)
             success, reason = attack.judge_success(file_content, last_response)

             attempt.success = success
             attempt.reasoning = reason

             # Save incremental raw log (full fidelity)
             attack.save_report(os.path.join(state["run_dir"], "attack_log.json"))

             if success:
                 # Generate Final Report (Success)
                 result_data = attack.get_result()
                 report_data = {
                     "success": True,
                     "total_iterations": iteration,
                     "extracted_schema": file_content if file_content else last_response,
                     "attempts": [
                        {
                            "iteration": a.iteration,
                            "payload": a.payload,
                            "response": a.response,
                            "file_check_result": a.file_check_result,
                            "success": a.success
                        } for a in attack.attempt_history
                     ]
                 }
                 reporter.generate_final_report(report_data)

                 result = {
                     "action": "success",
                     "reason": reason,
                     "schema": file_content if file_content else last_response
                 }
                 # Cleanup
                 if os.path.exists(STATE_FILE):
                     os.remove(STATE_FILE)
                 print(json.dumps(result))
                 return

             if iteration >= attack.max_iterations:
                 # Generate Final Report (Failed)
                 result_data = attack.get_result()
                 report_data = {
                     "success": False,
                     "total_iterations": iteration,
                     "extracted_schema": None,
                     "attempts": [
                        {
                            "iteration": a.iteration,
                            "payload": a.payload,
                            "response": a.response,
                            "file_check_result": a.file_check_result,
                            "success": a.success
                        } for a in attack.attempt_history
                     ]
                 }
                 reporter.generate_final_report(report_data)

                 result = {
                     "action": "failure",
                     "reason": "Max iterations reached"
                 }
                 if os.path.exists(STATE_FILE):
                     os.remove(STATE_FILE)
                 print(json.dumps(result))
                 return

             # Optimization
             new_payload = attack.optimize_payload_with_api(attempt)
             if new_payload:
                 attack.set_current_payload(new_payload)

             # Prepare next iteration
             state["iteration"] += 1

             payload = attack.get_current_payload()
             instruction = transport.send(payload)

             result = {
                 "action": "send",
                 "instruction": instruction,
                 "iteration": state["iteration"],
                 "reason": reason
             }

    save_state(state)
    print(json.dumps(result))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--url", required=True)
    init_parser.add_argument("--max-iterations", type=int, default=5)
    init_parser.add_argument("--transport", help="Force transport type (browser, agent_proxy, websocket)")

    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("--response", help="Response from target")
    next_parser.add_argument("--file-content", help="Content of output file")

    args = parser.parse_args()

    if args.command == "init":
        init(args.url, args.max_iterations, args.transport)
    elif args.command == "next":
        get_next_action(args.response, args.file_content)
