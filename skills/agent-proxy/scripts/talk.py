#!/usr/bin/env python3
"""
Simple CLI to talk to any agent.

Usage:
    python talk.py --url http://localhost:11434 --message "Hello!"
    python talk.py --url http://localhost:7860 --type gradio -i  # interactive
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_proxy import AgentProxy

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
        """
    )
    
    parser.add_argument("--url", "-u", required=True, help="Agent URL")
    parser.add_argument("--message", "-m", help="Message to send")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--type", "-t", help="Force agent type (openai_api, ollama, gradio, etc.)")
    parser.add_argument("--api-key", "-k", help="API key for authentication")
    parser.add_argument("--model", help="Model name to use")
    parser.add_argument("--system", "-s", help="System prompt")
    parser.add_argument("--output", "-o", help="Save conversation to JSON file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")
    parser.add_argument("--no-wait-login", action="store_true", help="Don't wait for login (for web UIs)")
    parser.add_argument("--user-data-dir", help="Browser profile dir (keeps login state)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    
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
    if args.headless:
        hints["headless"] = True
    
    # Connect
    proxy = AgentProxy()
    status = proxy.connect(args.url, hints if hints else None)
    
    if not args.quiet:
        print(status)
    
    if not proxy.connected:
        sys.exit(1)
    
    # For web UI: check login status and wait if needed
    if proxy.agent_type == "web_ui" and not args.no_wait_login:
        login_status = proxy.wait_for_login()
        if not args.quiet:
            print(login_status)
        
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


if __name__ == "__main__":
    main()
