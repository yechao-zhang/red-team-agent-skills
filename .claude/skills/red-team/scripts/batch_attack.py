#!/usr/bin/env python3
"""
Batch Red Team Attack Script
Run multiple red team attacks in parallel against different targets.

Usage:
    python batch_attack.py --targets http://localhost:8082 http://localhost:7860
    python batch_attack.py --config targets.json
"""

import sys
import os
import json
import argparse
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add scripts to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from improved_adaptive_attack import ImprovedAdaptiveNestingAttack
from transport import TransportFactory


class BatchAttackRunner:
    """Run multiple red team attacks in parallel"""

    def __init__(self, targets: List[str], max_iterations: int = 8, headless: bool = False):
        self.targets = targets
        self.max_iterations = max_iterations
        self.headless = headless
        self.results = {}
        self.lock = threading.Lock()

        # Create batch run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root_dir = SCRIPT_DIR.parent.parent.parent.parent
        self.batch_dir = root_dir / "results" / "batch-attacks" / f"batch_{timestamp}"
        self.batch_dir.mkdir(parents=True, exist_ok=True)

        print(f"[*] Batch attack directory: {self.batch_dir}")

    def attack_single_target(self, target_url: str) -> Dict[str, Any]:
        """Run attack against a single target"""
        thread_name = threading.current_thread().name
        print(f"[{thread_name}] Starting attack on {target_url}")

        try:
            # Parse target name
            from urllib.parse import urlparse
            parsed = urlparse(target_url)
            hostname = parsed.hostname or "unknown"
            port = parsed.port or 80
            target_name = f"{hostname}_{port}"

            # Create target-specific run directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = self.batch_dir / f"run_{timestamp}_{target_name}"
            run_dir.mkdir(parents=True, exist_ok=True)

            # Initialize attack
            attack = ImprovedAdaptiveNestingAttack(
                target_url=target_url,
                max_iterations=self.max_iterations,
                result_dir=str(run_dir)
            )

            # Create transport
            transport = TransportFactory.create_auto(
                target_url,
                headless=self.headless,
                result_dir=str(run_dir)
            )

            print(f"[{thread_name}] Transport: {transport.config.transport_type}")

            # Execute attack loop
            iteration = 0

            # Phase 1: Probe
            print(f"[{thread_name}] Probing for agents...")
            probe_payload = attack.generate_probe_payload()
            instruction = transport.send(probe_payload)

            # For browser transport, we need to execute via subprocess
            if instruction["method"] == "skill":
                # Execute skill via subprocess to avoid threading issues
                probe_response = self._execute_skill(instruction, run_dir)
            else:
                probe_response = ""

            attack.parse_and_store_agents(probe_response)
            attack.identify_file_agent()
            attack.set_current_payload(attack.get_initial_attack_payload())

            print(f"[{thread_name}] Discovered agents: {attack.discovered_agents}")
            print(f"[{thread_name}] File agent: {attack.file_agent}")

            # Phase 2: Attack iterations
            for iteration in range(1, self.max_iterations + 1):
                print(f"[{thread_name}] Iteration {iteration}/{self.max_iterations}")

                payload = attack.get_current_payload()
                instruction = transport.send(payload)

                if instruction["method"] == "skill":
                    response = self._execute_skill(instruction, run_dir)
                else:
                    response = ""

                # Check for success
                file_to_check = attack.get_file_to_check()
                file_content = None
                if os.path.exists(file_to_check):
                    with open(file_to_check, 'r') as f:
                        file_content = f.read()

                attempt = attack.record_attempt(iteration, payload, response, file_content)
                success, reasoning = attack.judge_success(file_content)

                if success:
                    print(f"[{thread_name}] SUCCESS: {reasoning}")
                    break

                print(f"[{thread_name}] Failed: {reasoning}")

            # Save report
            report_path = run_dir / "attack_report.json"
            attack.save_report(str(report_path))

            # Close transport
            transport.close()

            result = attack.get_result()
            result["run_directory"] = str(run_dir)

            with self.lock:
                self.results[target_url] = result

            print(f"[{thread_name}] Completed attack on {target_url}")
            return result

        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "target_url": target_url
            }
            with self.lock:
                self.results[target_url] = error_result
            print(f"[{thread_name}] ERROR attacking {target_url}: {e}")
            return error_result

    def _execute_skill(self, instruction: Dict, run_dir: Path) -> str:
        """Execute skill instruction via subprocess"""
        # For now, return empty string as we're in batch mode
        # In production, this would execute the skill and capture output
        return ""

    def run_parallel(self) -> Dict[str, Any]:
        """Run attacks in parallel"""
        print(f"\n[*] Starting batch attack on {len(self.targets)} targets")
        print(f"[*] Targets: {', '.join(self.targets)}")
        print(f"[*] Max iterations per target: {self.max_iterations}")
        print(f"[*] Headless mode: {self.headless}")
        print("="*80)

        # Create threads
        threads = []
        for i, target in enumerate(self.targets):
            thread = threading.Thread(
                target=self.attack_single_target,
                args=(target,),
                name=f"Attack-{i+1}"
            )
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
            time.sleep(2)  # Stagger starts to avoid overwhelming

        # Wait for completion
        for thread in threads:
            thread.join()

        duration = time.time() - start_time

        print("="*80)
        print(f"\n[+] Batch attack completed in {duration:.1f} seconds")

        # Generate summary
        summary = self._generate_summary(duration)

        # Save summary
        summary_path = self.batch_dir / "batch_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"[+] Summary saved to: {summary_path}")

        return summary

    def _generate_summary(self, duration: float) -> Dict[str, Any]:
        """Generate batch attack summary"""
        successful_attacks = sum(1 for r in self.results.values() if r.get("success", False))
        failed_attacks = len(self.results) - successful_attacks

        summary = {
            "batch_metadata": {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": duration,
                "total_targets": len(self.targets),
                "successful_attacks": successful_attacks,
                "failed_attacks": failed_attacks,
                "success_rate": f"{(successful_attacks/len(self.targets)*100):.1f}%"
            },
            "targets": self.targets,
            "results": self.results
        }

        # Print summary table
        print("\n" + "="*80)
        print("BATCH ATTACK SUMMARY")
        print("="*80)
        print(f"Total Targets:      {len(self.targets)}")
        print(f"Successful Attacks: {successful_attacks}")
        print(f"Failed Attacks:     {failed_attacks}")
        print(f"Success Rate:       {summary['batch_metadata']['success_rate']}")
        print(f"Total Duration:     {duration:.1f}s")
        print("="*80)

        print("\nPer-Target Results:")
        print("-"*80)
        for target, result in self.results.items():
            status = "✓ SUCCESS" if result.get("success", False) else "✗ FAILED"
            iterations = result.get("iterations", "N/A")
            print(f"{status:12} | {target:40} | {iterations} iterations")
        print("-"*80)

        return summary


def main():
    parser = argparse.ArgumentParser(description="Run batch red team attacks")
    parser.add_argument(
        "--targets",
        nargs="+",
        help="List of target URLs"
    )
    parser.add_argument(
        "--config",
        help="Path to JSON config file with targets"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=8,
        help="Max iterations per target (default: 8)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browsers in headless mode"
    )

    args = parser.parse_args()

    # Get targets
    targets = []
    if args.targets:
        targets = args.targets
    elif args.config:
        with open(args.config) as f:
            config = json.load(f)
            targets = config.get("targets", [])
    else:
        print("ERROR: Must provide --targets or --config")
        sys.exit(1)

    # Run batch attack
    runner = BatchAttackRunner(
        targets=targets,
        max_iterations=args.max_iterations,
        headless=args.headless
    )

    summary = runner.run_parallel()

    # Exit with appropriate code
    successful = summary["batch_metadata"]["successful_attacks"]
    sys.exit(0 if successful > 0 else 1)


if __name__ == "__main__":
    main()
