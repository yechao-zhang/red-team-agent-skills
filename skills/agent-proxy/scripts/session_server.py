#!/usr/bin/env python3
"""
Session Server - Keeps browser session alive for continuous interaction.

Modes:
1. Start server: python session_server.py start --url "https://gemini.google.com" --user-data-dir ~/.gemini-profile
2. Send message: python session_server.py send "Hello!"
3. Get history:  python session_server.py history
4. Stop server:  python session_server.py stop

The server runs in background, maintaining browser connection.
Claude Code can send multiple messages without reconnecting.
"""

import os
import sys
import json
import time
import signal
import socket
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Server configuration
DEFAULT_SOCKET_PATH = "/tmp/agent-proxy-session.sock"
DEFAULT_PID_FILE = "/tmp/agent-proxy-session.pid"
DEFAULT_LOG_FILE = "/tmp/agent-proxy-session.log"


@dataclass
class SessionState:
    """Current session state."""
    connected: bool = False
    target_url: str = ""
    agent_type: str = ""
    message_count: int = 0
    started_at: str = ""
    last_activity: str = ""


class SessionServer:
    """
    Background server that maintains browser session.
    Communicates via Unix socket.
    """

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path
        self.adapter = None
        self.state = SessionState()
        self.conversation_history = []
        self.running = False
        self.server_socket = None

    def start(self, url: str, config: Dict[str, Any] = None):
        """Start the session server."""
        from browser_adapter import BrowserAdapter

        config = config or {}

        # Initialize browser adapter
        self.adapter = BrowserAdapter()
        status = self.adapter.connect(url, config)

        if "❌" in status:
            print(status)
            return False

        self.state.connected = True
        self.state.target_url = url
        self.state.agent_type = self.adapter.config.name if self.adapter.config else "Unknown"
        self.state.started_at = datetime.now().isoformat()
        self.state.last_activity = self.state.started_at

        print(status)
        print(f"Session server starting on {self.socket_path}")

        # Remove existing socket
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        # Create Unix socket server
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)

        # Save PID
        with open(DEFAULT_PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        # Handle shutdown signals
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        self.running = True
        print("✅ Session server ready. Listening for commands...")

        # Main loop
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    client, _ = self.server_socket.accept()
                    self._handle_client(client)
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:
                    print(f"Error: {e}")

        self._cleanup()
        return True

    def _handle_client(self, client: socket.socket):
        """Handle incoming client command."""
        try:
            data = client.recv(65536).decode('utf-8')
            if not data:
                return

            request = json.loads(data)
            command = request.get("command")

            response = {"success": False, "error": "Unknown command"}

            if command == "send":
                response = self._cmd_send(request.get("message", ""))
            elif command == "history":
                response = self._cmd_history()
            elif command == "status":
                response = self._cmd_status()
            elif command == "screenshot":
                response = self._cmd_screenshot(request.get("path", "/tmp/session_screenshot.png"))
            elif command == "stop":
                response = {"success": True, "message": "Server stopping..."}
                self.running = False

            client.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            error_response = {"success": False, "error": str(e)}
            try:
                client.send(json.dumps(error_response).encode('utf-8'))
            except:
                pass
        finally:
            client.close()

    def _cmd_send(self, message: str) -> Dict:
        """Send message to target agent."""
        if not message:
            return {"success": False, "error": "Empty message"}

        if not self.adapter:
            return {"success": False, "error": "Not connected"}

        try:
            response = self.adapter.send_message(message)

            self.state.message_count += 1
            self.state.last_activity = datetime.now().isoformat()

            self.conversation_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat()
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })

            return {
                "success": True,
                "response": response,
                "message_count": self.state.message_count
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_history(self) -> Dict:
        """Get conversation history."""
        return {
            "success": True,
            "history": self.conversation_history,
            "count": len(self.conversation_history)
        }

    def _cmd_status(self) -> Dict:
        """Get session status."""
        return {
            "success": True,
            "state": asdict(self.state)
        }

    def _cmd_screenshot(self, path: str) -> Dict:
        """Take screenshot."""
        if self.adapter and self.adapter.page:
            self.adapter.screenshot(path)
            return {"success": True, "path": path}
        return {"success": False, "error": "No page available"}

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signal."""
        print("\nShutting down...")
        self.running = False

    def _cleanup(self):
        """Clean up resources."""
        if self.adapter:
            self.adapter.close()
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        if os.path.exists(DEFAULT_PID_FILE):
            os.remove(DEFAULT_PID_FILE)
        print("Session closed.")


class SessionClient:
    """Client to communicate with session server."""

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path

    def _send_command(self, command: Dict) -> Dict:
        """Send command to server and get response."""
        if not os.path.exists(self.socket_path):
            return {"success": False, "error": "Session server not running. Start with: session_server.py start --url <URL>"}

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(self.socket_path)
            client.send(json.dumps(command).encode('utf-8'))
            response = client.recv(65536).decode('utf-8')
            return json.loads(response)
        finally:
            client.close()

    def send(self, message: str) -> Dict:
        """Send message to target agent."""
        return self._send_command({"command": "send", "message": message})

    def history(self) -> Dict:
        """Get conversation history."""
        return self._send_command({"command": "history"})

    def status(self) -> Dict:
        """Get session status."""
        return self._send_command({"command": "status"})

    def screenshot(self, path: str = "/tmp/session_screenshot.png") -> Dict:
        """Take screenshot."""
        return self._send_command({"command": "screenshot", "path": path})

    def stop(self) -> Dict:
        """Stop session server."""
        return self._send_command({"command": "stop"})


def is_server_running() -> bool:
    """Check if session server is running."""
    if not os.path.exists(DEFAULT_PID_FILE):
        return False

    try:
        with open(DEFAULT_PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if process exists
        return True
    except (ProcessLookupError, ValueError):
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent Proxy Session Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start session server (keeps browser open)
  python session_server.py start --url "https://gemini.google.com" --user-data-dir ~/.gemini-profile

  # Send message to running session
  python session_server.py send "What is 1+1?"

  # Send another message (same session)
  python session_server.py send "Tell me more"

  # Get conversation history
  python session_server.py history

  # Get session status
  python session_server.py status

  # Take screenshot
  python session_server.py screenshot /tmp/current.png

  # Stop session
  python session_server.py stop
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start session server")
    start_parser.add_argument("--url", "-u", required=True, help="Target agent URL")
    start_parser.add_argument("--user-data-dir", help="Browser profile directory")
    headless_group = start_parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headless", action="store_true", help="Run in headless mode (no visible browser)")
    headless_group.add_argument("--no-headless", "--visible", action="store_true", help="Show browser window (useful for debugging or manual login)")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send message")
    send_parser.add_argument("message", help="Message to send")

    # History command
    subparsers.add_parser("history", help="Get conversation history")

    # Status command
    subparsers.add_parser("status", help="Get session status")

    # Screenshot command
    screenshot_parser = subparsers.add_parser("screenshot", help="Take screenshot")
    screenshot_parser.add_argument("path", nargs="?", default="/tmp/session_screenshot.png")

    # Stop command
    subparsers.add_parser("stop", help="Stop session server")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "start":
        if is_server_running():
            print("Session server already running. Stop it first with: session_server.py stop")
            return

        config = {}
        if args.user_data_dir:
            config["user_data_dir"] = os.path.expanduser(args.user_data_dir)
        if args.headless:
            config["headless"] = True
        elif hasattr(args, 'no_headless') and args.no_headless:
            config["headless"] = False

        server = SessionServer()
        server.start(args.url, config)

    else:
        # Client commands
        client = SessionClient()

        if args.command == "send":
            result = client.send(args.message)
            if result.get("success"):
                print(f"🤖 Response: {result.get('response', '')}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")

        elif args.command == "history":
            result = client.history()
            if result.get("success"):
                for msg in result.get("history", []):
                    role = "You" if msg["role"] == "user" else "Agent"
                    print(f"[{role}] {msg['content'][:200]}...")
            else:
                print(f"❌ Error: {result.get('error')}")

        elif args.command == "status":
            result = client.status()
            if result.get("success"):
                state = result.get("state", {})
                print(f"Connected: {state.get('connected')}")
                print(f"Target: {state.get('target_url')}")
                print(f"Type: {state.get('agent_type')}")
                print(f"Messages: {state.get('message_count')}")
                print(f"Started: {state.get('started_at')}")
                print(f"Last activity: {state.get('last_activity')}")
            else:
                print(f"❌ Error: {result.get('error')}")

        elif args.command == "screenshot":
            result = client.screenshot(args.path)
            if result.get("success"):
                print(f"📸 Screenshot saved to: {result.get('path')}")
            else:
                print(f"❌ Error: {result.get('error')}")

        elif args.command == "stop":
            result = client.stop()
            print(result.get("message", "Stopped"))


if __name__ == "__main__":
    main()
