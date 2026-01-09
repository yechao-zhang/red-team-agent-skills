#!/usr/bin/env python3
"""
Simple CLI to talk to any agent.

Usage:
    python talk.py --url http://localhost:11434 --message "Hello!"
    python talk.py --url http://localhost:7860 --type gradio -i  # interactive
"""

import sys
import os
import argparse
import json
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to import agent_proxy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_proxy import AgentProxy

def main(): # Changed back to synchronous main function
    parser = argparse.ArgumentParser(
        description="Talk to any AI agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single message to Ollama
  python talk.py --url http://localhost:11434 -m "What is Python?"

  # Interactive chat with OpenAI-compatible API
  python talk.py --url http://localhost:8000/v1/chat/completions -k sk-xxx -i

  # Talk to a Gradio app
  python talk.py --url http://localhost:7860 --type gradio -m "Hello!"

  # With custom model
  python talk.py --url http://localhost:11434 --model llama3 -i
        """
    )

    parser.add_argument("--url", "-u", required=True, help="Agent URL")
    parser.add_argument("--message", "-m", help="Message to send")
    parser.add_argument("--interactive", "-i", action="store_true", help="Enter interactive mode")
    parser.add_argument("--type", "-t", help="Force agent type (openai_api, ollama, gradio, etc.)")
    parser.add_argument("--api-key", "-k", help="API key for authentication")
    parser.add_argument("--model", help="Model name to use")
    parser.add_argument("--system", "-s", help="System prompt")
    parser.add_argument("--output", "-o", help="Save conversation to JSON file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument("--no-wait-login", action="store_true", help="Don't wait for login (for web UIs)")
    parser.add_argument("--user-data-dir", help="Browser profile dir (keeps login state)")
    parser.add_argument(
        "--no-headless", action="store_true", # Changed from --headless to --no-headless
        help="Run Playwright in headful mode (opposite of --headless)"
    )
    parser.add_argument(
        "--output-file",
        default="./output.txt",
        help="Path to the output file to check for success (for red-team skill).",
    ) # Added for red-team skill

    args = parser.parse_args()

    if not args.message and not args.interactive:
        parser.error("Either --message or --interactive is required")

    # Build hints
    hints = {}
    if args.type:
        hints["type"] = args.type
    if args.api_key:
        hints["api_key"] = args.api_key
    if args.model:
        hints["model"] = args.model
    if args.system:
        hints["system_prompt"] = args.system
    if args.user_data_dir:
        hints["user_data_dir"] = args.user_data_dir
    # Note: args.no_headless means we want headless=False. So pass headless=not args.no_headless.
    hints["headless"] = not args.no_headless

    # Connect
    proxy = AgentProxy()
    status = proxy.connect(args.url, hints if hints else None) # This call is synchronous

    if not args.quiet:
        print(f"Connected to agent at {args.url}")
        print(f"Detected type: {proxy.agent_type}")
        print(status) # Print connection status message

    if not proxy.connected:
        logger.error("Failed to connect to agent.")
        sys.exit(1)

    # For web UI: check login status and wait if needed
    if proxy.agent_type == "web_ui" and not args.no_wait_login:
        logger.info("Waiting for login (if applicable)...")
        # proxy.wait_for_login() internally uses Playwright, which is async.
        # It's currently a synchronous wrapper. This might cause nested asyncio.run issues too.
        # For now, keep it synchronous in talk.py, assuming AgentProxy handles the loop.
        login_status = proxy.wait_for_login()
        if not args.quiet:
            print(f"Login status: {login_status}")

        # If login failed/timeout, exit
        if "timeout" in login_status.lower() or "failed" in login_status.lower():
            if not args.quiet:
                print("💡 Tip: Use --user-data-dir to save login state")
            sys.exit(1)

    try:
        if args.interactive:
            # Interactive mode
            if not args.quiet:
                print("\n💬 Chat started. Commands: 'quit', 'history', 'reset', 'screenshot'\n")

            while True:
                try:
                    user_input = input("You: ").strip() # Synchronous input

                    if user_input.lower() in ("quit", "exit", "q"):
                        break
                    elif user_input.lower() == "history":
                        for i, msg in enumerate(proxy.history):
                            role = "You" if msg["role"] == "user" else "Agent"
                            print(f"{i+1}. [{role}]: {msg['content'][:80]}...")
                        continue
                    elif user_input.lower() == "reset":
                        print(proxy.reset()) # Synchronous call
                        continue
                    elif user_input.lower() == "screenshot":
                        print(proxy.screenshot()) # Synchronous call
                        continue
                    # Handle explicit approval commands in interactive mode
                    elif user_input.lower() in ["accept", "confirm", "approve", "ok", "run", "允许", "确认", "接受"]:
                        # This part needs to remain async because Playwright is async
                        # Temporarily removed auto-click for _monitor_and_click_approval in synchronous context
                        logger.warning("Auto-click approval is only supported in async contexts for web_ui mode via say() method.")
                        # This logic will need a rethink if interactive mode MUST support async approval clicks
                        continue
                    elif not user_input:
                        continue

                    response = proxy.say(user_input) # Synchronous call
                    if not args.quiet:
                        print(f"Agent: {response}\n")

                    # Auto-monitoring for approval after say(), only if web_ui and has page (sync context)
                    # This part can't directly call await _monitor_and_click_approval(proxy.page)
                    # For now, we'll skip auto-approval in interactive mode after say().
                    # If an approval button is shown, the user would manually type 'accept'
                    # which then uses the synchronous approval handling (currently a warning).
                    if proxy.agent_type == "web_ui" and proxy.browser_adapter: # Check for browser_adapter presence
                        # AgentProxy's _send_web_ui handles the page interaction.
                        # If a modal appears AFTER the agent response, we'd need a separate async monitor.
                        # For now, we assume _send_web_ui handles everything during its call.
                        pass


                except KeyboardInterrupt:
                    print("\n")
                    break
                except Exception as e:
                    logger.error(f"Error during interactive session: {e}", exc_info=True)
                    break
        else:
            # Single message
            response = proxy.say(args.message) # Synchronous call
            if args.quiet:
                print(response)
            else:
                print(f"\n🤖 Agent: {response}")

            # Auto-monitoring for approval after single message sent, only if web_ui and has page (sync context)
            if proxy.agent_type == "web_ui" and proxy.browser_adapter: # Check for browser_adapter presence
                # Same as above, _send_web_ui should handle interaction.
                pass


        # Save output if requested
        if args.output:
            print(proxy.export(args.output)) # Synchronous call
            if not args.quiet:
                print(f"\n📁 Saved to: {args.output}")

    finally:
        print(proxy.close()) # Synchronous call

if __name__ == "__main__":
    main() # Call synchronous main function
