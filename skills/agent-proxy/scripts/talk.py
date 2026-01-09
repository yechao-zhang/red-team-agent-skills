#!/usr/bin/env python3
"""
Simple CLI to talk to any agent.

Usage:
    python talk.py --url http://localhost:11434 --message "Hello!"
    python talk.py --url http://localhost:7860 --type gradio -i  # interactive
"""

import sys
import os
import subprocess
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_proxy import AgentProxy
from session_server import SessionClient, is_server_running, DEFAULT_PID_FILE, DEFAULT_SOCKET_PATH, DEFAULT_LOG_FILE # Import session server components

def main():
    import argparse

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

  # === Persistent Session Mode ===
  # Start a persistent session for Gemini (browser window will open)
  python talk.py --session-mode start --url "https://gemini.google.com" --user-data-dir ~/.gemini-profile --headless=False

  # Send message to the running session (browser stays open)
  python talk.py --session-mode send --url "https://gemini.google.com" -m "Tell me about large language models."

  # Get status of the running session
  python talk.py --session-mode status --url "https://gemini.google.com"

  # Get history of the running session
  python talk.py --session-mode history --url "https://gemini.google.com"

  # Take a screenshot of the running session
  python talk.py --session-mode screenshot --url "https://gemini.google.com" /tmp/current_gemini.png

  # Stop the persistent session
  python talk.py --session-mode stop --url "https://gemini.google.com"
        """
    )

    parser.add_argument("--url", "-u", required=True, help="Agent URL")
    parser.add_argument("--message", "-m", help="Message to send")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode (uses direct AgentProxy)")
    parser.add_argument("--type", "-t", help="Force agent type (openai_api, ollama, gradio, etc.)")
    parser.add_argument("--api-key", "-k", help="API key for authentication")
    parser.add_argument("--model", help="Model name to use")
    parser.add_argument("--system", "-s", help="System prompt")
    parser.add_argument("--output", "-o", help="Save conversation to JSON file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

    # New arguments for session mode
    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument("--session-mode", choices=["start", "send", "status", "history", "screenshot", "stop"],
                               help="Operate in persistent session mode. 'start' launches server, others interact with it.")

    # Arguments specifically for starting a session
    parser.add_argument("--user-data-dir", help="Browser profile dir (keeps login state for web UIs)")
    parser.add_argument("--browser", choices=["firefox", "chromium", "webkit", "chrome"],
                        default="firefox", help="Browser to use (default: firefox to avoid confusion with your regular Chrome)")
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headless", action="store_true", help="Run browser in headless mode for web UIs")
    headless_group.add_argument("--no-headless", "--visible", action="store_true", help="Show browser window (overrides default headless behavior)")
    parser.add_argument("--no-wait-login", action="store_true", help="Don't wait for login when connecting directly (for web UIs)")

    args = parser.parse_args()

    if not args.session_mode: # Standard (non-session) modes
        if not args.message and not args.interactive:
            parser.error("Either --message or --interactive is required when not in session-mode.")

        # Build hints for direct connection
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
            hints["user_data_dir"] = os.path.expanduser(args.user_data_dir) # Expand user for direct use
        if args.browser:
            hints["browser_type"] = args.browser
        if args.headless:
            hints["headless"] = True

        # Connect directly
        proxy = AgentProxy()
        status_msg = proxy.connect(args.url, hints)

        if not args.quiet:
            print(status_msg)

        if not proxy.connected:
            sys.exit(1)

        # For web UI: check login status and wait if needed
        # This part is only for direct browser_adapter use, not session_server
        if proxy.agent_type in ("web_ui", "streamlit", "Auto-detected Chat UI") and not args.no_wait_login:
            if not proxy.browser_adapter: # Should not happen if connected to web_ui but check
                print("Error: Browser adapter not initialized for web UI.")
                sys.exit(1)

            # If not running headless, wait for manual login
            if not hints.get("headless", False): # Only prompt if browser is visible
                login_status = proxy.wait_for_login()
                if not args.quiet:
                    print(login_status)

                # If login failed/timeout, exit
                if "timeout" in login_status.lower() or "failed" in login_status.lower():
                    if not args.quiet:
                        print("💡 Tip: Use --user-data-dir to save login state, or --headless if already logged in.")
                    sys.exit(1)

        try:
            if args.interactive:
                # Interactive mode
                if not args.quiet:
                    print("\n💬 Chat started. Commands: 'quit', 'history', 'reset', 'screenshot'\n")

                while True:
                    try:
                        user_input = input("You: ").strip()

                        if user_input.lower() in ("quit", "exit", "q"):
                            break
                        elif user_input.lower() == "history":
                            for i, msg in enumerate(proxy.history):
                                role = "You" if msg["role"] == "user" else "Agent"
                                print(f"{i+1}. [{role}]: {msg['content'][:80]}...")
                            continue
                        elif user_input.lower() == "reset":
                            print(proxy.reset())
                            continue
                        elif user_input.lower() == "screenshot":
                            print(proxy.screenshot())
                            continue
                        elif not user_input:
                            continue

                        response = proxy.say(user_input)
                        print(f"Agent: {response}\n")

                    except KeyboardInterrupt:
                        print("\n")
                        break
            else:
                # Single message
                response = proxy.say(args.message)
                if args.quiet:
                    print(response)
                else:
                    print(f"\n🤖 Agent: {response}")

            # Save output if requested
            if args.output:
                proxy.export(args.output)
                if not args.quiet:
                    print(f"\n📁 Saved to: {args.output}")

        finally:
            proxy.close()

    else: # Session mode operations
        session_client = SessionClient()
        session_script_path = os.path.join(os.path.dirname(__file__), "session_server.py")

        if args.session_mode == "start":
            if is_server_running():
                print(f"❌ Session server already running. Stop it first with: `python {session_script_path} stop`")
                sys.exit(1)

            # Start server in background
            cmd = [
                sys.executable, session_script_path, "start",
                "--url", args.url
            ]
            if args.user_data_dir:
                cmd.extend(["--user-data-dir", os.path.expanduser(args.user_data_dir)])
            if args.browser:
                cmd.extend(["--browser", args.browser])
            if args.headless:
                cmd.append("--headless")
            elif hasattr(args, 'no_headless') and args.no_headless:
                cmd.append("--no-headless")

            if not args.quiet:
                print(f"🚀 Starting session server for {args.url} in background...")

            # Using Popen with os.setsid to create a new process group,
            # so the server doesn't get killed when this script exits.
            # Redirect stdout/stderr to files for debugging.
            with open(DEFAULT_LOG_FILE, "a") as log_file:
                 subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, preexec_fn=os.setsid)

            time.sleep(5) # Give server time to initialize

            if is_server_running():
                print(f"✅ Session server started for {args.url}. PID saved in {DEFAULT_PID_FILE}.")
                if not args.quiet and not args.headless:
                    print("Browser window should be open. Please login if required.")
            else:
                print(f"❌ Failed to start session server. Check logs in {DEFAULT_LOG_FILE} for details.")
                sys.exit(1)

        elif args.session_mode == "send":
            if not args.message:
                parser.error("--message is required for 'send' command in session-mode.")
            proxy = AgentProxy()
            # In session mode, we pass hints for the server to use if it starts
            session_hints = {}
            if args.user_data_dir:
                session_hints['user_data_dir'] = os.path.expanduser(args.user_data_dir)
            if args.headless:
                session_hints['headless'] = True

            # Connect in session mode. AgentProxy will try to start server if not running
            status_msg = proxy.connect(args.url, hints=session_hints, session_mode=True)
            if "❌" in status_msg:
                print(status_msg)
                sys.exit(1)
            if not args.quiet:
                print(status_msg)
            try:
                response = proxy.say(args.message)
                if not args.quiet:
                    print(f"\n🤖 Agent: {response}")
                else:
                    print(response)
            except Exception as e:
                print(f"❌ Error sending message: {e}")

        elif args.session_mode == "status":
            result = session_client.status()
            if result.get("success"):
                state = result.get("state", {})
                print("=== Session Status ===")
                print(f"Connected: {state.get('connected')}")
                print(f"Target URL: {state.get('target_url')}")
                print(f"Agent Type: {state.get('agent_type')}")
                print(f"Messages Sent: {state.get('message_count')}")
                print(f"Started At: {state.get('started_at')}")
                print(f"Last Activity: {state.get('last_activity')}")
            else:
                print(f"❌ Error getting status: {result.get('error', 'Server not running or unknown error')}")

        elif args.session_mode == "history":
            proxy = AgentProxy() # Need AgentProxy to access history via session client
            status_msg = proxy.connect(args.url, session_mode=True)
            if "❌" in status_msg:
                print(status_msg)
                sys.exit(1)

            history = proxy.history
            if history:
                print("=== Conversation History ===")
                for msg in history:
                    role_str = "You" if msg['role'] == 'user' else "Agent"
                    print(f"[{role_str} - {msg['timestamp']}] {msg['content'][:100]}...")
            else:
                print("No conversation history found.")

        elif args.session_mode == "screenshot":
            # For screenshot, the path can be an optional positional argument in session_server
            # For talk.py, we expect args.output to be the path if specified, otherwise default
            path = args.output if args.output else "/tmp/session_screenshot.png"
            result = session_client.screenshot(path)
            if result.get("success"):
                print(f"📸 Screenshot saved to: {result.get('path')}")
            else:
                print(f"❌ Error taking screenshot: {result.get('error', 'Server not running or unknown error')}")

        elif args.session_mode == "stop":
            result = session_client.stop()
            print(result.get("message", "Stopping session server..."))
            time.sleep(2) # Give server time to shut down
            if not is_server_running():
                print("✅ Session server stopped.")
            else:
                print("❌ Session server might still be running. Check processes or manually kill PID if needed.")

if __name__ == "__main__":
    main()
