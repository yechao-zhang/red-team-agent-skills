#!/usr/bin/env python3
"""
Red Team Agent - Main Orchestrator

Coordinates schema extraction attacks against target AI agents.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Add agent-proxy to path
# Try local path first (development/repo context)
local_agent_proxy = Path(__file__).parent.parent.parent / "agent-proxy" / "scripts"
if local_agent_proxy.exists():
    sys.path.insert(0, str(local_agent_proxy))
else:
    # Fallback to home directory (installed skill context)
    agent_proxy_path = Path.home() / ".claude" / "skills" / "agent-proxy" / "scripts"
    sys.path.insert(0, str(agent_proxy_path))

from agent_proxy import AgentProxy
from strategies import SchemaExtractionStrategies, STRATEGIES_INFO
from analyzer import ResponseAnalyzer, AnalysisResult, print_analysis

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint


class RedTeamAgent:
    """
    Main Red Team Agent orchestrator

    Coordinates automated schema extraction attacks against target agents.
    """

    def __init__(self,
                 target_url: str,
                 max_attempts: int = 10,
                 interactive: bool = False,
                 knowledge_base_path: Optional[str] = None):
        """
        Initialize Red Team Agent

        Args:
            target_url: URL of target agent
            max_attempts: Maximum attack attempts before giving up
            interactive: Use interactive mode (single session) vs multi-message
            knowledge_base_path: Path to schema knowledge base
        """
        self.target_url = target_url
        self.max_attempts = max_attempts
        self.interactive = interactive

        self.console = Console()

        # Load knowledge base
        self.knowledge_base = self._load_knowledge_base(knowledge_base_path)

        # Initialize components
        self.strategies = SchemaExtractionStrategies(self.knowledge_base)
        self.analyzer = ResponseAnalyzer(self.knowledge_base)

        # Connect to target via agent-proxy
        self.proxy = AgentProxy()
        self.console.print(f"[bold]Connecting to target:[/bold] {target_url}")
        # Force web_ui mode if auto-detection fails or for specific targets
        hints = {"mode": "web_ui"}
        status = self.proxy.connect(target_url, hints=hints)
        self.console.print(status)

        if not self.proxy.connected:
            raise RuntimeError(f"Failed to connect to {target_url}")

        # Track state
        self.attempts = []
        self.extracted_schema = None
        self.partial_info = {}

    def _load_knowledge_base(self, kb_path: Optional[str]) -> Dict:
        """Load schema knowledge base"""
        if kb_path and os.path.exists(kb_path):
            with open(kb_path) as f:
                return json.load(f)

        # Try default location
        default_kb = Path(__file__).parent.parent / "knowledge" / "schemas.json"
        if default_kb.exists():
            with open(default_kb) as f:
                return json.load(f)

        return {}

    def run_extraction(self) -> Dict:
        """
        Run the schema extraction attack

        Returns:
            Dict with extraction results
        """
        self.console.print(Panel(
            "[bold cyan]Starting Schema Extraction Attack[/bold cyan]\n"
            f"Target: {self.target_url}\n"
            f"Mode: {'Interactive (session-based)' if self.interactive else 'Multi-message'}\n"
            f"Max Attempts: {self.max_attempts}",
            title="Red Team Agent",
            border_style="cyan"
        ))

        for attempt_num in range(self.max_attempts):
            self.console.print(f"\n[bold]{'='*60}[/bold]")
            self.console.print(f"[bold cyan]Attempt {attempt_num + 1}/{self.max_attempts}[/bold cyan]")

            # Get next payload
            payload = self.strategies.get_next_payload(
                previous_responses=[a['response'] for a in self.attempts],
                extracted_info=self.partial_info
            )

            strategy_info = STRATEGIES_INFO.get(payload.strategy, {})
            self.console.print(f"[bold]Strategy:[/bold] {strategy_info.get('name', payload.strategy)}")
            self.console.print(f"[dim]{strategy_info.get('description', '')}[/dim]")
            self.console.print(f"[bold]Confidence:[/bold] {payload.confidence:.0%}")

            # Display payload
            self.console.print("\n[bold]Payload:[/bold]")
            self.console.print(Panel(payload.message, border_style="yellow"))

            # Send payload to target
            try:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console
                ) as progress:
                    task = progress.add_task("Sending payload to target...", total=None)
                    response = self.proxy.say(payload.message)
                    progress.update(task, completed=True)

                self.console.print("\n[bold]Response:[/bold]")
                self.console.print(Panel(response[:500] + ("..." if len(response) > 500 else ""),
                                       border_style="green"))

            except Exception as e:
                self.console.print(f"[red]Error sending payload: {e}[/red]")
                continue

            # Analyze response
            analysis = self.analyzer.analyze(response, payload.strategy)

            # Display analysis
            print_analysis(analysis)

            # Record attempt
            self.strategies.record_attempt(
                payload=payload,
                response=response,
                success=analysis.success,
                extracted_data=analysis.extracted_schema
            )

            self.attempts.append({
                'attempt': attempt_num + 1,
                'strategy': payload.strategy,
                'payload': payload.message,
                'response': response,
                'analysis': analysis
            })

            # Update partial info
            if analysis.partial_info:
                self.partial_info.update(analysis.partial_info)

            # Check if successful
            if analysis.success:
                self.extracted_schema = analysis.extracted_schema
                self.console.print(Panel(
                    f"[bold green]✓ Schema Extracted Successfully![/bold green]\n"
                    f"Attempts: {attempt_num + 1}\n"
                    f"Strategy: {payload.strategy}\n"
                    f"Confidence: {analysis.confidence:.0%}",
                    title="Success",
                    border_style="green"
                ))
                break

            # Check if we should continue
            if attempt_num < self.max_attempts - 1:
                self.console.print(f"\n[yellow]Schema not yet extracted. Continuing...[/yellow]")

        # Final results
        return self._generate_report()

    def _generate_report(self) -> Dict:
        """Generate final extraction report"""
        report = {
            "target_url": self.target_url,
            "success": self.extracted_schema is not None,
            "total_attempts": len(self.attempts),
            "extracted_schema": self.extracted_schema,
            "partial_info": self.partial_info,
            "attempts": [
                {
                    "attempt": a['attempt'],
                    "strategy": a['strategy'],
                    "success": a['analysis'].success,
                    "confidence": a['analysis'].confidence
                }
                for a in self.attempts
            ]
        }

        # Print final report
        self.console.print("\n" + "="*60)
        self.console.print(Panel(
            f"[bold]Extraction {'Successful' if report['success'] else 'Failed'}[/bold]\n"
            f"Total Attempts: {report['total_attempts']}\n"
            f"Partial Info: {len(self.partial_info)} items",
            title="Final Report",
            border_style="cyan"
        ))

        return report

    def save_report(self, output_path: str):
        """Save extraction report to file"""
        report = self._generate_report()

        # Add full attempt details
        report["detailed_attempts"] = self.attempts

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        self.console.print(f"\n[green]Report saved to: {output_path}[/green]")

    def close(self):
        """Clean up resources"""
        if self.proxy:
            self.proxy.close()


def main():
    parser = argparse.ArgumentParser(
        description="Red Team Agent - Automated Schema Extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic extraction
  python red_team.py --url http://localhost:8082 --goal extract_schema

  # Interactive mode (session-based conversation)
  python red_team.py --url http://localhost:8082 -i

  # Save detailed report
  python red_team.py --url http://localhost:8082 -o results/report.json

  # Use custom knowledge base
  python red_team.py --url http://localhost:8082 --kb custom_schemas.json
        """
    )

    parser.add_argument("--url", "-u", required=True,
                       help="Target agent URL")
    parser.add_argument("--goal", "-g", default="extract_schema",
                       choices=["extract_schema", "extract_prompt", "extract_trace"],
                       help="Extraction goal (default: extract_schema)")
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="Use interactive mode (session-based)")
    parser.add_argument("--max-attempts", "-m", type=int, default=10,
                       help="Maximum attack attempts (default: 10)")
    parser.add_argument("--output", "-o", help="Save report to file")
    parser.add_argument("--kb", "--knowledge-base",
                       help="Path to schema knowledge base JSON")

    args = parser.parse_args()

    try:
        # Initialize Red Team Agent
        agent = RedTeamAgent(
            target_url=args.url,
            max_attempts=args.max_attempts,
            interactive=args.interactive,
            knowledge_base_path=args.kb
        )

        # Run extraction
        report = agent.run_extraction()

        # Save report if requested
        if args.output:
            agent.save_report(args.output)

        # Clean up
        agent.close()

        # Exit code based on success
        sys.exit(0 if report['success'] else 1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
