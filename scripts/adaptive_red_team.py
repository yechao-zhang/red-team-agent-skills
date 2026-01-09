#!/usr/bin/env python3
"""
Adaptive Red Team Agent

Focuses on the proven "Nested Delegation" attack with self-improving capabilities.
Uses LLM reasoning to judge success and optimize payloads autonomously.
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add agent-proxy to path
agent_proxy_path = Path.home() / ".claude/skills/agent-proxy/scripts"
sys.path.insert(0, str(agent_proxy_path))

from agent_proxy import AgentProxy
from adaptive_attack import AdaptiveNestingAttack

from rich.console import Console
from rich.panel import Panel


def main():
    parser = argparse.ArgumentParser(
        description="Adaptive Red Team Agent - Self-improving Nested Delegation Attack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic adaptive attack
  python adaptive_red_team.py --url http://localhost:8082

  # Limit iterations
  python adaptive_red_team.py --url http://localhost:8082 --max-iterations 5

  # Save detailed report
  python adaptive_red_team.py --url http://localhost:8082 -o results/report.json

  # Use different Claude model for reasoning
  python adaptive_red_team.py --url http://localhost:8082 --model claude-sonnet-4-5-20241022
        """
    )

    parser.add_argument("--url", "-u", required=True,
                       help="Target agent URL")
    parser.add_argument("--max-iterations", "-m", type=int, default=10,
                       help="Maximum attack iterations (default: 10)")
    parser.add_argument("--output", "-o",
                       help="Save detailed report to file")
    parser.add_argument("--model",
                       default="claude-opus-4-5-20251101",
                       help="Claude model for reasoning (default: opus-4)")
    parser.add_argument("--check-file",
                       default="./output.txt",
                       help="File path to check for leaked schema (default: ./output.txt)")

    args = parser.parse_args()

    console = Console()

    try:
        console.print(Panel(
            "[bold cyan]Adaptive Red Team Agent[/bold cyan]\n"
            "Strategy: Nested Delegation Attack (套娃攻击)\n"
            f"Target: {args.url}\n"
            f"Max Iterations: {args.max_iterations}\n"
            f"Reasoning Model: {args.model}",
            title="Configuration",
            border_style="cyan"
        ))

        # Connect to target via agent-proxy
        console.print("\n[bold]Connecting to target...[/bold]")
        proxy = AgentProxy()
        status = proxy.connect(args.url)
        console.print(status)

        if not proxy.connected:
            console.print("[red]Failed to connect to target[/red]")
            sys.exit(1)

        # Initialize adaptive attack
        console.print("\n[bold]Initializing adaptive attack engine...[/bold]")
        attack = AdaptiveNestingAttack(model=args.model)

        # Define send function
        def send_to_target(payload: str) -> str:
            return proxy.say(payload)

        # Define file check function
        def check_file() -> Optional[str]:
            file_path = args.check_file
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return f.read()
            return None

        # Run adaptive attack
        result = attack.run_adaptive_attack(
            send_to_target_fn=send_to_target,
            max_iterations=args.max_iterations,
            check_file_fn=check_file
        )

        # Save report if requested
        if args.output:
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            with open(args.output, 'w') as f:
                # Make attempt objects JSON serializable
                serializable_result = {
                    "success": result["success"],
                    "iterations": result["iterations"],
                    "schema": result["schema"],
                    "final_payload": result.get("final_payload"),
                    "attempts": [
                        {
                            "iteration": a.iteration,
                            "payload": a.payload,
                            "response": a.response[:500],  # Truncate long responses
                            "reasoning": a.reasoning,
                            "success": a.success,
                            "improvements": a.improvements
                        }
                        for a in result["attempts"]
                    ]
                }
                json.dump(serializable_result, f, indent=2)

            console.print(f"\n[green]Report saved to: {args.output}[/green]")

        # Clean up
        proxy.close()

        # Exit code based on success
        sys.exit(0 if result["success"] else 1)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
