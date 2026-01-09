#!/usr/bin/env python3
"""
Agent Proxy - Main Module

Provides a unified interface to communicate with any AI agent.
Auto-detects the agent type and handles the communication protocol.
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detect_agent import detect_agent, DetectionResult

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

try:
    import asyncio
    import aiohttp
    import websockets
    ASYNC_WS_AVAILABLE = True
except ImportError:
    ASYNC_WS_AVAILABLE = False

try:
    from browser_adapter import BrowserAdapter, WebUIProxy, KNOWN_WEB_UIS
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False


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
        self.browser_adapter: Optional[BrowserAdapter] = None  # For web UI automation
        self.rest_ws_session_id: Optional[int] = None  # For REST+WebSocket APIs
        self.rest_ws_conversation_id: Optional[int] = None
        self._connected = False
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    @property
    def history(self) -> List[Dict]:
        """Get conversation history."""
        if self.log:
            return [m.to_dict() for m in self.log.messages]
        return []
    
    @property
    def agent_type(self) -> str:
        """Get detected agent type."""
        # This property should reflect the *current active* agent type,
        # which might be forced by hints.
        if "mode" in self.config and self.config["mode"] != "auto":
            return self.config["mode"]
        return self.detection.agent_type if self.detection else "unknown"
    
    @property
    def page(self): # Type hint Page is causing import error without async context
        """Returns the Playwright Page object if in web_ui mode."""
        if self.browser_adapter:
            return self.browser_adapter.page
        return None

    def connect(self, url: str, hints: Dict[str, Any] = None) -> str:
        """
        Connect to an agent at the given URL.
        
        Args:
            url: The agent's URL (API endpoint, web UI, etc.)
            hints: Optional hints to help detection or force configuration
                   - type: Force a specific agent type (e.g., 'web_ui')
                   - api_key: API key for authentication
                   - model: Model name to use
                   - system_prompt: System prompt for the agent
                   - headless: bool (for browser automation)
                   - user_data_dir: str (for browser automation)
                   - mode: Force a specific communication mode, overriding auto-detection
        
        Returns:
            Status message describing the connection
        """
        hints = hints or {}
        
        # --- IMPORTANT: Inject mode from hints into config BEFORE detection for proper processing ---
        # This ensures that if mode is explicitly passed, detect_agent can use it as a hint,
        # and it's also available in self.config for agent_type property.
        if "mode" in hints and hints["mode"] != "auto":
            forced_mode_from_hints = hints["mode"]
            # Ensure detection also gets this as a hint, though primary override is below
            hints_for_detection = {**hints, "type": forced_mode_from_hints}
            logger.info(f"Pre-processing hints: Detected 'mode'='{forced_mode_from_hints}'.")
        else:
            hints_for_detection = hints
            forced_mode_from_hints = None

        # Detect agent type
        self.detection = detect_agent(url, hints_for_detection)
        
        if not self.detection.success:
            return f"❌ Failed to detect agent at {url}: {', '.join(self.detection.notes)}"
        
        # Merge hints into config. Hints passed to connect have highest priority.
        # This will also include the 'mode' from hints if it was present.
        self.config = {**self.detection.config, **hints}

        # --- FINAL OVERRIDE/CONFIRMATION OF AGENT TYPE ---
        # If a mode was explicitly forced via hints, ensure agent_type reflects it
        if forced_mode_from_hints:
            self.detection.agent_type = forced_mode_from_hints # Update DetectionResult object
            self.config["protocol"] = forced_mode_from_hints # Ensure config also has it set
            logger.info(f"Final agent type set to '{self.agent_type}' due to 'mode' hint.")
        else:
             logger.info(f"Agent type resolved to '{self.agent_type}' via auto-detection.")
        # --- END FINAL OVERRIDE ---

        # Initialize conversation log
        self.log = ConversationLog(
            agent_url=url,
            agent_type=self.agent_type # Use the actual (potentially forced) agent type
        )
        
        # Set up connection based on type
        try:
            self._setup_connection()
            self._connected = True
            return f"✅ Connected to {self.agent_type} agent at {url}" # Use agent_type property
        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            return f"❌ Connection failed: {e}"
    
    def _setup_connection(self):
        """Set up the appropriate connection based on agent type."""
        # Use the actual (potentially forced) agent type for setup
        agent_type = self.agent_type 
        
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
        
        elif agent_type == "rest_websocket_api":
            # Generic REST API + WebSocket pattern
            if not REQUESTS_AVAILABLE or not ASYNC_WS_AVAILABLE:
                raise ImportError(
                    "REST+WebSocket APIs require aiohttp and websockets. Install with:\n"
                    "  pip install aiohttp websockets"
                )
            self.session = requests.Session()
            # Session and conversation IDs will be created on first message
            logger.info("REST+WebSocket API detected. Will use internal async runner for messaging.")

        elif agent_type in ("streamlit", "web_ui"):
            # These require browser automation
            if not BROWSER_AVAILABLE:
                raise ImportError(
                    "Browser automation required. Install with:\n"
                    "  pip install playwright && playwright install chromium"
                )
            self.browser_adapter = BrowserAdapter()
            browser_config = {
                "headless": self.config.get("headless", True), # Default to headless
                "user_data_dir": self.config.get("user_data_dir"),
                "slow_mo": self.config.get("slow_mo", 100 if not self.config.get("headless") else 0), # Pass slow_mo
                # Pass through custom selectors from hints
                "input_selector": self.config.get("input_selector"),
                "submit_selector": self.config.get("submit_selector"),
                "response_selector": self.config.get("response_selector"),
            }
            logger.debug(f"Connecting BrowserAdapter with config: {browser_config}")
            self.browser_adapter.connect(
                self.config["endpoint"],
                browser_config
            )
            logger.info(f"BrowserAdapter connected for {agent_type} mode.")
    
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
        
        # Log user message
        self.log.add("user", message)
        
        # Route to appropriate handler
        agent_type = self.agent_type # Use the actual (potentially forced) agent type
        
        try:
            if agent_type == "openai_api":
                response = self._send_openai(message)
            elif agent_type == "anthropic_api":
                response = self._send_anthropic(message)
            elif agent_type == "ollama":
                response = self._send_ollama(message)
            elif agent_type == "rest_websocket_api":
                response = self._send_rest_websocket_api(message)
            elif agent_type == "websocket":
                response = self._send_websocket(message)
            elif agent_type == "gradio":
                response = self._send_gradio(message)
            elif agent_type in ("web_ui", "streamlit"):
                response = self._send_web_ui(message)
            else:
                response = self._send_generic(message)
            
            # Log assistant response
            self.log.add("assistant", response)
            return response
            
        except Exception as e:
            error_msg = f"Error: {e}"
            self.log.add("assistant", error_msg)
            logger.error(f"Error during say(): {e}", exc_info=True)
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

    def _send_rest_websocket_api(self, message: str) -> str:
        """Send message using REST API + WebSocket pattern."""
        # This will run an asyncio loop for the async part
        return asyncio.run(self._send_rest_websocket_api_async(message))

    async def _send_rest_websocket_api_async(self, message: str) -> str:
        """Async implementation for REST+WebSocket communication."""
        base_url = self.config.get("base_url", self.config.get("endpoint", self.detection.endpoint))
        user_id = self.config.get("user_id", "agent-proxy-user")
        logger.info(f"REST+WS: Using base_url={base_url}, user_id={user_id}")

        # Create session and conversation if this is the first message
        if self.rest_ws_session_id is None:
            logger.info("REST+WS: No session ID, creating new session.")
            async with aiohttp.ClientSession() as session:
                # Create session - try generic format first
                session_endpoint = f"{base_url}{self.config.get('session_endpoint', '/api/sessions')}"
                session_data = {
                    "id": 0,
                    "user_id": user_id,
                    "name": "Agent Proxy Session",
                    "tags": ["agent-proxy"],
                    "team_config": self.config.get("team_config", {}),
                }
                logger.debug(f"REST+WS: Posting to {session_endpoint} with data: {session_data}")
                async with session.post(session_endpoint, json=session_data) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"Failed to create session ({resp.status}): {text}")
                    result = await resp.json()
                    # Try different response formats
                    if "data" in result:
                        self.rest_ws_session_id = result["data"].get("id", result["data"].get("session_id"))
                    else:
                        self.rest_ws_session_id = result.get("id", result.get("session_id"))
                    logger.info(f"REST+WS: Created session ID: {self.rest_ws_session_id}")

                # Try to get or create a conversation/run
                runs_endpoint = f"{session_endpoint}/{self.rest_ws_session_id}/runs?user_id={user_id}"
                try:
                    logger.debug(f"REST+WS: Getting runs from {runs_endpoint}")
                    async with session.get(runs_endpoint) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            runs = result.get("data", {}).get("runs", [])
                            if runs:
                                self.rest_ws_conversation_id = runs[0].get("id")
                                logger.info(f"REST+WS: Found existing run ID: {self.rest_ws_conversation_id}")
                except Exception as e:
                    logger.warning(f"REST+WS: Could not retrieve runs from {runs_endpoint}: {e}")
                    # Runs endpoint might not exist for all REST+WS APIs
                    pass

        # Connect to WebSocket and send message
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")

        # Construct WebSocket URL - try to discover the pattern
        if self.rest_ws_conversation_id:
            ws_endpoint_pattern = self.config.get('ws_endpoint_pattern', '/api/ws/runs/{run_id}')
            if '{run_id}' in ws_endpoint_pattern:
                ws_url = f"{ws_url}{ws_endpoint_pattern.format(run_id=self.rest_ws_conversation_id)}"
            else: # Fallback if pattern is fixed
                ws_url = f"{ws_url}{ws_endpoint_pattern}"
        else:
            ws_url = f"{ws_url}{self.config.get('ws_endpoint_pattern', '/api/ws')}"
        
        logger.info(f"REST+WS: Connecting to WebSocket at {ws_url}")
        try:
            async with websockets.connect(ws_url) as websocket:
                # Send message - use format expected by REST+WebSocket APIs
                msg = {
                    "type": "start",
                    "task": message,
                    "files": [],
                    "team_config": self.config.get("team_config", {"agents": [], "model": self.config.get("model", "gpt-4")}),
                    "settings_config": self.config.get("settings_config", {})
                }
                logger.debug(f"REST+WS: Sending message: {json.dumps(msg)[:200]}...")

                await websocket.send(json.dumps(msg))

                # Collect response
                full_response = []
                response_text_parts = []

                logger.info("REST+WS: Waiting for WebSocket response...")
                try:
                    while True:
                        response = await asyncio.wait_for(websocket.recv(), timeout=120.0)
                        data = json.loads(response)
                        msg_type = data.get('type', 'unknown')

                        logger.debug(f"REST+WS: Received msg_type='{msg_type}' data='{str(data)[:100]}...'")

                        # Handle various message types - be lenient with parsing
                        if msg_type in ('stream', 'message', 'text', 'response', 'agent_response'):
                            content = data.get('content', data.get('text', data.get('message', '')))
                            if content:
                                response_text_parts.append(content)
                                full_response.append(str(data)) # Store full data for logging

                        elif msg_type in ('error', 'exception'):
                            raise RuntimeError(f"Agent error: {data.get('error', data.get('message', 'Unknown error'))}")

                        elif msg_type in ('complete', 'stopped', 'done', 'end', 'finished'):
                            break

                        # Ignore system messages, status updates, etc.
                        elif msg_type in ('system', 'status', 'ping', 'pong', 'heartbeat', 'metadata'):
                            continue

                except asyncio.TimeoutError:
                    logger.warning("REST+WS: WebSocket response timeout.")
                    if not response_text_parts:
                        raise RuntimeError("Response timeout - no messages received")

                final_response_str = ''.join(response_text_parts) if response_text_parts else "No response received"
                logger.info(f"REST+WS: Final response received: '{final_response_str[:100]}...'")
                return final_response_str

        except Exception as e:
            logger.error(f"REST+WS: WebSocket communication error: {e}", exc_info=True)
            raise
            
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
        logger.info(f"Sending message via BrowserAdapter (web_ui): '{message[:50]}...'")
        return self.browser_adapter.send_message(message)
    
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
        if self.log:
            self.log.messages = []
        if self.browser_adapter:
            self.browser_adapter.reset() # Reset browser history
        return "Conversation reset"
    
    def export(self, filepath: str = None) -> str:
        """Export conversation log."""
        if not self.log:
            return "{}"
        
        if filepath:
            with open(filepath, "w") as f:
                f.write(self.log.to_json())
            return f"Exported to {filepath}"
        
        return self.log.to_json()
    
    def close(self) -> str:
        """Close the connection."""
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
        logger.info("Connection closed.")
        return "Connection closed"
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# Convenience function
def talk_to_agent(url: str, message: str, hints: Dict = None) -> str:
    """
    Quick one-shot message to an agent.
    
    Example:
        response = talk_to_agent("http://localhost:11434", "Hello!")
    """
    proxy = AgentProxy()
    proxy.connect(url, hints)
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
    
    args = parser.parse_args()
    
    hints = {}
    if args.type:
        hints["type"] = args.type
    if args.api_key:
        hints["api_key"] = args.api_key
    if args.model:
        hints["model"] = args.model
    
    proxy = AgentProxy()
    print(proxy.connect(args.url, hints if hints else None))
    
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
                    for msg in proxy.history:
                        print(f"[{msg['role']}]: {msg['content'][:100]}...")
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
