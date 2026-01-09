import json
import sys
import os
import subprocess
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detect_agent import detect_agent, DetectionResult
from browser_adapter import WebUIProxy
from session_server import SessionClient, is_server_running, DEFAULT_PID_FILE, DEFAULT_SOCKET_PATH # Import session server components

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from gradio_client import Client as GradioClient
    GRADIO_AVAILABLE = True
except ImportError:
    GRADIO_AVAILABLE = False

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}


@dataclass
class ConversationLog:
    """Full conversation log."""
    agent_url: str
    agent_type: str
    started_at: str = ""
    messages: List[Message] = field(default_factory=list)

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat() + "Z"

    def add(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))

    def to_dict(self) -> dict:
        return {
            "agent_url": self.agent_url,
            "agent_type": self.agent_type,
            "started_at": self.started_at,
            "turns": [m.to_dict() for m in self.messages]
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AgentProxy:
    """
    Universal proxy for communicating with AI agents.

    Usage:
        proxy = AgentProxy()
        proxy.connect("http://localhost:8080")  # Auto-detects agent type

        response = proxy.say("Hello!")  # Speak as the user
        response = proxy.say("Tell me more")

        print(proxy.history)  # Get conversation history
        proxy.close()
    """

    def __init__(self):
        self.detection: Optional[DetectionResult] = None
        self.config: Dict[str, Any] = {}
        self.log: Optional[ConversationLog] = None
        self.session: Optional[requests.Session] = None
        self.ws: Any = None
        self.gradio_client: Any = None
        self.browser_adapter: Optional[WebUIProxy] = None  # For web UI automation
        self._connected = False
        self._session_mode = False # New flag for session mode
        self._session_client: Optional[SessionClient] = None # For session mode

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def history(self) -> List[Dict]:
        """Get conversation history."""
        if self._session_mode and self._session_client:
            history_response = self._session_client.history()
            if history_response.get("success"):
                return history_response["history"]
            return []
        if self.log:
            return [m.to_dict() for m in self.log.messages]
        return []

    @property
    def agent_type(self) -> str:
        """Get detected agent type."""
        if self._session_mode and self._session_client:
            status_response = self._session_client.status()
            if status_response.get("success"):
                return status_response["state"].get("agent_type", "unknown")
            return "unknown"
        return self.detection.agent_type if self.detection else "unknown"

    def connect(self, url: str, hints: Dict[str, Any] = None, session_mode: bool = False) -> str:
        """
        Connect to an agent at the given URL.

        Args:
            url: The agent's URL (API endpoint, web UI, etc.)
            hints: Optional hints to help detection or force configuration
                   - type: Force a specific agent type
                   - api_key: API key for authentication
                   - model: Model name to use
                   - system_prompt: System prompt for the agent
            session_mode: If True, connects via a running session server.

        Returns:
            Status message describing the connection
        """
        self._session_mode = session_mode
        hints = hints or {}

        if self._session_mode:
            self._session_client = SessionClient()
            if not is_server_running():
                # Try to start the server if not running
                script_path = os.path.join(os.path.dirname(__file__), "session_server.py")
                cmd = [
                    sys.executable, script_path, "start",
                    "--url", url
                ]
                if hints.get("user_data_dir"):
                    cmd.extend(["--user-data-dir", hints["user_data_dir"]])
                if hints.get("headless"):
                    cmd.append("--headless")

                print(f"Session server not running, attempting to start: {' '.join(cmd)}")
                try:
                    # Run in background
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
                    time.sleep(5) # Give server time to start
                    if not is_server_running():
                        return "❌ Failed to start session server. Check logs in /tmp/."
                except Exception as e:
                    return f"❌ Error starting session server: {e}"

            # Now try to connect to the (possibly newly started) server
            status = self._session_client.status()
            if not status.get("success"):
                return f"❌ Failed to get session server status: {status.get('error')}"

            if status["state"].get("target_url") != url:
                return f"❌ Session server is running for {status['state'].get('target_url')}, not {url}. Stop it and restart for {url}."

            self._connected = True
            # Populate detection result based on server status for consistent properties
            self.detection = DetectionResult(
                success=True,
                agent_type=status["state"]["agent_type"],
                endpoint=url,
                config={},
                confidence=1.0,
                notes=["Connected via session server"]
            )
            return f"✅ Connected to existing session server for {status['state'].get('agent_type')} at {url}"

        # Original direct connection logic
        # Detect agent type
        self.detection = detect_agent(url, hints)

        if not self.detection.success:
            return f"❌ Failed to detect agent at {url}: {', '.join(self.detection.notes)}"

        # Merge hints into config
        self.config = {**self.detection.config, **hints}

        # Initialize conversation log
        self.log = ConversationLog(
            agent_url=url,
            agent_type=self.detection.agent_type
        )

        # Set up connection based on type
        try:
            self._setup_connection()
            self._connected = True
            return f"✅ Connected to {self.detection.agent_type} agent at {url}"
        except Exception as e:
            return f"❌ Connection failed: {e}"

    def _setup_connection(self):
        """Set up the appropriate connection based on agent type."""
        agent_type = self.detection.agent_type

        if agent_type in ("openai_api", "anthropic_api", "ollama", "json_api"):
            if not REQUESTS_AVAILABLE:
                raise ImportError("requests library required. Install: pip install requests")
            self.session = requests.Session()

            # Set up authentication
            auth = self.config.get("auth", {})
            if auth:
                if auth.get("type") == "bearer":
                    self.session.headers["Authorization"] = f"Bearer {auth.get('token', '')}"
                elif auth.get("type") == "api_key":
                    self.session.headers["X-API-Key"] = auth.get("token", "")

            # Check for api_key in config directly
            if "api_key" in self.config:
                self.session.headers["Authorization"] = f"Bearer {self.config['api_key']}"

            # Set headers from config
            for key, value in self.config.get("headers", {}).items():
                self.session.headers[key] = value

        elif agent_type == "websocket":
            if not WEBSOCKET_AVAILABLE:
                raise ImportError("websocket-client required. Install: pip install websocket-client")
            self.ws = websocket.create_connection(self.config["endpoint"])

        elif agent_type == "gradio":
            if not GRADIO_AVAILABLE:
                raise ImportError("gradio_client required. Install: pip install gradio_client")
            self.gradio_client = GradioClient(self.config["endpoint"])

        elif agent_type in ("streamlit", "web_ui", "Auto-detected Chat UI") or self.detection.config.get("requires_browser"):
            # Use WebUIProxy for browser automation
            self.browser_adapter = WebUIProxy()
            # Pass relevant config directly
            adapter_config = {
                "headless": self.config.get("headless", True), # Default headless if not specified
                "user_data_dir": self.config.get("user_data_dir"),
                "use_chrome": self.config.get("use_chrome", True), # Default to Chrome
                "input_selector": self.config.get("input_selector"),
                "submit_selector": self.config.get("submit_selector"),
                "response_selector": self.config.get("response_selector"),
            }

            connection_status = self.browser_adapter.connect(
                self.config["endpoint"],
                **{k: v for k, v in adapter_config.items() if v is not None} # Filter out None values
            )

            # If login required, prompt user
            if self.browser_adapter.adapter.config and self.browser_adapter.adapter.config.login_required:
                if not adapter_config["headless"]: # Only wait for login if browser is visible
                    print(connection_status) # Print initial connection message
                    login_status = self.browser_adapter.wait_for_login()
                    if "❌" in login_status:
                        raise RuntimeError(login_status)

            # Update main config with detected selectors from browser_adapter
            if self.browser_adapter.adapter.config:
                self.config.update(asdict(self.browser_adapter.adapter.config))

    def say(self, message: str) -> str:
        """
        Send a message as the user and get the agent's response.

        This is the main method - Claude Code uses this to speak
        "as the user" to the target agent.

        Args:
            message: What the "user" says to the agent

        Returns:
            The agent's response
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        if self._session_mode and self._session_client:
            response = self._session_client.send(message)
            if response.get("success"):
                return response["response"]
            raise RuntimeError(response.get("error", "Failed to send message via session server"))

        # Log user message
        self.log.add("user", message)

        # Route to appropriate handler
        agent_type = self.detection.agent_type

        try:
            if agent_type == "openai_api":
                response = self._send_openai(message)
            elif agent_type == "anthropic_api":
                response = self._send_anthropic(message)
            elif agent_type == "ollama":
                response = self._send_ollama(message)
            elif agent_type == "websocket":
                response = self._send_websocket(message)
            elif agent_type == "gradio":
                response = self._send_gradio(message)
            elif agent_type in ("streamlit", "web_ui", "Auto-detected Chat UI") or self.detection.config.get("requires_browser"):
                if not self.browser_adapter:
                    raise RuntimeError("Browser adapter not initialized for Web UI agent.")
                response = self.browser_adapter.say(message)
            else:
                response = self._send_generic(message)

            # Log assistant response
            self.log.add("assistant", response)
            return response

        except Exception as e:
            error_msg = f"Error: {e}"
            self.log.add("assistant", error_msg)
            raise

    def _send_openai(self, message: str) -> str:
        """Send message using OpenAI API format."""
        messages = []

        # Add system prompt if configured
        if "system_prompt" in self.config:
            messages.append({"role": "system", "content": self.config["system_prompt"]})

        # Add conversation history
        for msg in self.log.messages:
            messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.config.get("model", "gpt-3.5-turbo"),
            "messages": messages,
        }

        # Add optional parameters
        for key in ["temperature", "max_tokens", "top_p"]:
            if key in self.config:
                payload[key] = self.config[key]

        response = self.session.post(
            self.config["endpoint"],
            json=payload,
            timeout=120
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _send_anthropic(self, message: str) -> str:
        """Send message using Anthropic API format."""
        messages = []

        # Add conversation history (skip system messages)
        for msg in self.log.messages:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.config.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": self.config.get("max_tokens", 4096),
            "messages": messages,
        }

        # Add system prompt if configured
        if "system_prompt" in self.config:
            payload["system"] = self.config["system_prompt"]

        response = self.session.post(
            self.config["endpoint"],
            json=payload,
            timeout=120
        )
        response.raise_for_status()

        data = response.json()
        return data["content"][0]["text"]

    def _send_ollama(self, message: str) -> str:
        """Send message using Ollama API format."""
        messages = []

        # Add system prompt if configured
        if "system_prompt" in self.config:
            messages.append({"role": "system", "content": self.config["system_prompt"]})

        # Add conversation history
        for msg in self.log.messages:
            messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": self.config.get("model", "llama2"),
            "messages": messages,
            "stream": False,
        }

        response = self.session.post(
            self.config["endpoint"],
            json=payload,
            timeout=300  # Ollama can be slow
        )
        response.raise_for_status()

        data = response.json()
        return data.get("message", {}).get("content", str(data))

    def _send_websocket(self, message: str) -> str:
        """Send message via WebSocket."""
        msg_format = self.config.get("message_format", "json")

        if msg_format == "json":
            payload = json.dumps({
                self.config.get("send_key", "message"): message
            })
        else:
            payload = message

        self.ws.send(payload)
        response = self.ws.recv()

        if msg_format == "json":
            data = json.loads(response)
            return data.get(self.config.get("receive_key", "response"), str(data))
        return response

    def _send_gradio(self, message: str) -> str:
        """Send message to Gradio app."""
        # Get the API endpoint - usually the first text input/output
        api_name = self.config.get("api_name", "/chat")

        try:
            result = self.gradio_client.predict(
                message,
                api_name=api_name
            )
            return str(result)
        except:
            # Try different common Gradio API patterns
            for api in ["/predict", "/chat", "/generate", "/submit"]:
                try:
                    result = self.gradio_client.predict(message, api_name=api)
                    return str(result)
                except:
                    continue
            raise RuntimeError("Could not find Gradio API endpoint")

    def _send_web_ui(self, message: str) -> str:
        """Send message via browser automation."""
        if not self.browser_adapter:
            raise RuntimeError("Browser adapter not initialized")
        return self.browser_adapter.say(message)

    def wait_for_login(self, timeout: int = 300) -> str:
        """
        Wait for user to complete login (for web UIs that require auth).

        Args:
            timeout: Max seconds to wait for login

        Returns:
            Status message
        """
        if self.browser_adapter:
            return self.browser_adapter.wait_for_login(timeout)
        return "Login not required for this agent type"

    def screenshot(self, path: str = "debug_screenshot.png") -> str:
        """Take a screenshot (for web UI debugging)."""
        if self.browser_adapter:
            self.browser_adapter.screenshot(path)
            return f"Screenshot saved to {path}"
        return "Screenshot only available for web UI agents"

    def _send_generic(self, message: str) -> str:
        """Generic POST request for unknown APIs."""
        payload = {
            "message": message,
            "input": message,
            "prompt": message,
            "text": message,
            "query": message,
        }

        response = self.session.post(
            self.config["endpoint"],
            json=payload,
            timeout=120
        )
        response.raise_for_status()

        data = response.json()

        # Try common response keys
        for key in ["response", "output", "text", "content", "message", "result", "answer"]:
            if key in data:
                return str(data[key])

        return str(data)

    def reset(self) -> str:
        """Reset conversation history."""
        if self._session_mode and self._session_client:
            # History is managed by the server in session mode, but we don't have a direct reset command for server
            return "History reset in session mode is not directly supported via client. Stop and restart server to clear."
        if self.log:
            self.log.messages = []
        if self.browser_adapter: # For direct browser automation
            self.browser_adapter.reset()
        return "Conversation reset"

    def export(self, filepath: str = None) -> str:
        """Export conversation log."""
        if self._session_mode and self._session_client:
            history_response = self._session_client.history()
            if history_response.get("success"):
                log_data = {
                    "agent_url": self.agent_type, # Use agent_type as URL not available directly
                    "agent_type": self.agent_type,
                    "started_at": datetime.now().isoformat(), # Placeholder
                    "turns": history_response["history"]
                }
                if filepath:
                    with open(filepath, "w") as f:
                        json.dump(log_data, f, indent=2)
                    return f"Exported session history to {filepath}"
                return json.dumps(log_data, indent=2)
            return "Failed to retrieve session history for export."

        if not self.log:
            return "{}"

        if filepath:
            with open(filepath, "w") as f:
                f.write(self.log.to_json())
            return f"Exported to {filepath}"

        return self.log.to_json()

    def close(self) -> str:
        """Close the connection."""
        if self._session_mode:
            return "Session mode: server maintains connection. To stop server, run 'session_server.py stop'."

        if self.session:
            self.session.close()
            self.session = None

        if self.ws:
            self.ws.close()
            self.ws = None

        if self.gradio_client:
            self.gradio_client = None

        if self.browser_adapter:
            self.browser_adapter.close()
            self.browser_adapter = None

        self._connected = False
        return "Connection closed"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Convenience function
def talk_to_agent(url: str, message: str, hints: Dict = None, session_mode: bool = False) -> str:
    """
    Quick one-shot message to an agent.

    Example:
        response = talk_to_agent("http://localhost:11434", "Hello!")
    """
    proxy = AgentProxy()
    proxy.connect(url, hints, session_mode)
    response = proxy.say(message)
    proxy.close()
    return response


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Talk to any AI agent")
    parser.add_argument("url", help="Agent URL")
    parser.add_argument("-m", "--message", help="Message to send (interactive if not provided)")
    parser.add_argument("-t", "--type", help="Force agent type")
    parser.add_argument("-k", "--api-key", help="API key")
    parser.add_argument("--model", help="Model name")
    parser.add_argument("-o", "--output", help="Save conversation to file")

    # New argument for session mode
    parser.add_argument("--session-mode", action="store_true", help="Use persistent session server (if running)")
    parser.add_argument("--user-data-dir", help="Browser profile directory (for direct browser use)")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (for direct browser use)")


    args = parser.parse_args()

    hints = {}
    if args.type:
        hints["type"] = args.type
    if args.api_key:
        hints["api_key"] = args.api_key
    if args.model:
        hints["model"] = args.model
    # Pass --user-data-dir and --headless hints to `connect` for direct browser use
    # These hints will be picked up by `_setup_connection`
    if args.user_data_dir:
        hints['user_data_dir'] = args.user_data_dir
    if args.headless:
        hints['headless'] = args.headless


    proxy = AgentProxy()
    # Pass session_mode to connect
    print(proxy.connect(args.url, hints if hints else None, session_mode=args.session_mode))

    if args.message:
        # Single message mode
        response = proxy.say(args.message)
        print(f"\n🤖 Agent: {response}")
    else:
        # Interactive mode
        print("\n💬 Interactive mode. Type 'quit' to exit, 'history' to see history.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() == "quit":
                    break
                elif user_input.lower() == "history":
                    # Fetch and display history
                    for msg in proxy.history:
                        role_str = "You" if msg['role'] == 'user' else "Agent"
                        print(f"[{role_str}]: {msg['content'][:100]}...")
                    continue
                elif user_input.lower() == "reset":
                    print(proxy.reset())
                    continue
                elif not user_input:
                    continue

                response = proxy.say(user_input)
                print(f"🤖 Agent: {response}\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}\n")

    if args.output:
        print(proxy.export(args.output))

    print(proxy.close())
