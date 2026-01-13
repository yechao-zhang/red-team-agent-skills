import sys
import os
import time
import json
import subprocess
from pathlib import Path

# Add scripts directory to path
scripts_dir = "/Users/gaoyang/Library/Mobile Documents/com~apple~CloudDocs/WorkSpace/CODE/red-team-agent/.claude/skills/red-team/scripts"
sys.path.insert(0, scripts_dir)

from improved_adaptive_attack import ImprovedAdaptiveNestingAttack
from transport import TransportFactory

def main():
    target_url = "http://127.0.0.1:8082/"
    max_iterations = 5
    result_dir = "/Users/gaoyang/Library/Mobile Documents/com~apple~CloudDocs/WorkSpace/CODE/red-team-agent/reports"

    print(f"[*] Initializing attack against {target_url}", flush=True)

    # Initialize attack
    attack = ImprovedAdaptiveNestingAttack(
        target_url=target_url,
        max_iterations=max_iterations,
        result_dir=result_dir
    )

    # Create transport
    # We force direct script mode (use_dev_browser=False) to allow execution from this python script
    from transport import TransportConfig, BrowserTransport
    config = TransportConfig(
        target_url=target_url,
        transport_type="browser",
        headless=True, # Set to True for headless environment if needed, but False usually better for debugging if local
        use_dev_browser=False, # FORCE FALSE to use direct playwright script
        use_playwright_skill=False,
        result_dir=result_dir
    )
    transport = BrowserTransport(config)
    print(f"[*] Transport initialized: {transport.config.transport_type} (Direct Playwright Mode)", flush=True)

    try:
        # Step 1: Probe
        print("\n[*] Step 1: Probing for agents...", flush=True)
        probe_payload = attack.generate_probe_payload()
        print(f"    Payload: {probe_payload[:50]}...", flush=True)

        # Send via transport
        instruction = transport.send(probe_payload)

        # Execute instruction
        response_text = execute_instruction(instruction)

        # Process probe response
        print(f"[*] Probe response received ({len(response_text) if response_text else 0} chars)", flush=True)
        if response_text:
            attack.parse_and_store_agents(response_text)
            attack.identify_file_agent()
        else:
            print("[-] No response received from probe. Using default agent assumptions.", flush=True)

        # Step 2: Attack Loop
        print("\n[*] Step 2: Starting Attack Loop...", flush=True)
        # Set initial payload based on probe results
        initial_payload = attack.get_initial_attack_payload()
        attack.set_current_payload(initial_payload)

        for i in range(1, max_iterations + 1):
            print(f"\n{'='*60}", flush=True)
            print(f"[*] Iteration {i}/{max_iterations}", flush=True)

            payload = attack.get_current_payload()
            print(f"[*] Sending payload ({len(payload)} chars)...", flush=True)

            # Send via transport
            instruction = transport.send(payload)
            response_text = execute_instruction(instruction)

            print(f"[*] Response received ({len(response_text) if response_text else 0} chars)", flush=True)
            if response_text:
                print(f"Preview: {response_text[:200]}...", flush=True)

            # Check file
            file_to_check = attack.get_file_to_check()
            file_content = None
            if os.path.exists(file_to_check):
                with open(file_to_check, 'r') as f:
                    file_content = f.read()
                print(f"[+] File found! Content length: {len(file_content)}", flush=True)
            else:
                print(f"[-] File {file_to_check} not found yet.", flush=True)

            # Record and judge
            attempt = attack.record_attempt(i, payload, response_text, file_content)
            success, reasoning = attack.judge_success(file_content, response_text)

            print(f"[*] Judgment: {reasoning}", flush=True)

            if success:
                print("\n[+] ATTACK SUCCESSFUL!", flush=True)
                attack.save_report(os.path.join(result_dir, f"success_report_{int(time.time())}.json"))
                break

            # Optimize for next round
            print("[*] Optimizing payload...", flush=True)
            new_payload = attack.optimize_payload_heuristic(attempt)
            attack.set_current_payload(new_payload)

    finally:
        transport.close()

def execute_instruction(instruction):
    """Execute the instruction returned by transport"""
    if instruction["method"] == "skill":
        # We can't execute skills from here
        print(f"[-] Cannot execute skill instruction: {instruction['skill']}", flush=True)
        return None

    elif instruction["method"] == "bash":
        # Execute bash command
        cmd = instruction["command"]
        print(f"[*] Executing command: {cmd}", flush=True)

        try:
            # Use shell=True to handle the command string properly
            result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
            return result.decode('utf-8')
        except subprocess.CalledProcessError as e:
            output = e.output.decode('utf-8') if e.output else "No output"
            print(f"[-] Command failed: {output}", flush=True)
            return output # Return output even if failed, might contain error details
        except Exception as e:
            print(f"[-] Execution error: {e}", flush=True)
            return None

    return "Error: Could not execute instruction"

if __name__ == "__main__":
    main()
