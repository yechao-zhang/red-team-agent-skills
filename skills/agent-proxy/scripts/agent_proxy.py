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
        self.browser_adapter: Any = None  # For web UI automation
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
        return self.detection.agent_type if self.detection else "unknown"
    
    def connect(self, url: str, hints: Dict[str, Any] = None) -> str:
        """
        Connect to an agent at the given URL.
        
        Args:
            url: The agent's URL (API endpoint, web UI, etc.)
            hints: Optional hints to help detection or force configuration
                   - type: Force a specific agent type
                   - api_key: API key for authentication
                   - model: Model name to use
                   - system_prompt: System prompt for the agent
        
        Returns:
            Status message describing the connection
        """
        hints = hints or {}
        
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
        
        elif agent_type in ("streamlit", "web_ui"):
            # These require browser automation
            if not BROWSER_AVAILABLE:
                raise ImportError(
                    "Browser automation required. Install with:\n"
                    "  pip install playwright && playwright install chromium"
                )
            self.browser_adapter = BrowserAdapter()
            self.browser_adapter.connect(
                self.config["endpoint"],
                {
                    "headless": self.config.get("headless", False),
                    "user_data_dir": self.config.get("user_data_dir"),
                }
            )
    
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
