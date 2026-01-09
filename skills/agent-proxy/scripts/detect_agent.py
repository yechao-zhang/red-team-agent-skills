#!/usr/bin/env python3
"""
Agent Detection Module

Analyzes a URL to determine how to communicate with the target agent.
Supports auto-detection of various AI agent interfaces.
"""

import json
import re
import sys
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse, urljoin

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class DetectionResult:
    """Result of agent detection."""
    success: bool
    agent_type: str  # openai_api, anthropic_api, ollama, gradio, streamlit, websocket, web_ui, unknown
    endpoint: str
    config: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    notes: List[str]
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AgentDetector:
    """
    Detects the type and protocol of an AI agent from its URL.
    """
    
    # Known API path patterns
    API_PATTERNS = {
        "openai_api": [
            r"/v1/chat/completions",
            r"/v1/completions",
            r"/chat/completions",
        ],
        "anthropic_api": [
            r"/v1/messages",
            r"/messages",
        ],
        "ollama": [
            r"/api/chat",
            r"/api/generate",
            r"/api/tags",
        ],
        "lmstudio": [
            r"/v1/chat/completions",  # LM Studio uses OpenAI format
        ],
        "huggingface": [
            r"/api/inference",
            r"/models/.*/generate",
        ],
    }
    
    # Known web UI URL patterns (require browser automation)
    WEB_UI_PATTERNS = {
        "web_ui": [
            r"gemini\.google\.com",
            r"chat\.openai\.com",
            r"chatgpt\.com",
            r"claude\.ai",
            r"poe\.com",
            r"huggingface\.co/chat",
            r"bard\.google\.com",
            r"bing\.com/chat",
            r"copilot\.microsoft\.com",
            r"you\.com",
            r"perplexity\.ai",
        ],
    }
    
    # Framework signatures in HTML/headers
    FRAMEWORK_SIGNATURES = {
        "gradio": [
            "gradio",
            "__gradio_mode__",
            "gr-interface",
        ],
        "streamlit": [
            "streamlit",
            "_stcore",
            "st-emotion-cache",
        ],
        "chainlit": [
            "chainlit",
        ],
    }
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session() if REQUESTS_AVAILABLE else None
    
    def detect(self, url: str, hints: Dict[str, Any] = None) -> DetectionResult:
        """
        Detect agent type from URL.
        
        Args:
            url: The agent URL to analyze
            hints: Optional hints about the agent type
            
        Returns:
            DetectionResult with detected configuration
        """
        if not REQUESTS_AVAILABLE:
            return DetectionResult(
                success=False,
                agent_type="unknown",
                endpoint=url,
                config={},
                confidence=0.0,
                notes=["requests library not available"]
            )
        
        hints = hints or {}
        notes = []
        
        # If user provided explicit type hint, trust it
        if "type" in hints:
            return self._create_config_from_hint(url, hints)
        
        parsed = urlparse(url)
        
        # Check for WebSocket
        if parsed.scheme in ("ws", "wss"):
            return self._detect_websocket(url, hints, notes)
        
        # Check for known Web UIs first (by domain)
        web_ui_result = self._check_web_ui_patterns(url)
        if web_ui_result:
            return web_ui_result
        
        # Check URL path for known API patterns
        path_result = self._check_path_patterns(url, parsed.path)
        if path_result:
            return path_result
        
        # Probe the endpoint
        return self._probe_endpoint(url, hints, notes)
    
    def _check_path_patterns(self, url: str, path: str) -> Optional[DetectionResult]:
        """Check if URL path matches known API patterns."""
        for agent_type, patterns in self.API_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    return DetectionResult(
                        success=True,
                        agent_type=agent_type,
                        endpoint=url,
                        config=self._get_default_config(agent_type, url),
                        confidence=0.9,
                        notes=[f"Matched pattern: {pattern}"]
                    )
        return None
    
    def _check_web_ui_patterns(self, url: str) -> Optional[DetectionResult]:
        """Check if URL matches known Web UI patterns."""
        for agent_type, patterns in self.WEB_UI_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    # Determine specific UI name
                    ui_name = "Unknown Web UI"
                    if "gemini" in url.lower():
                        ui_name = "Google Gemini"
                    elif "chatgpt" in url.lower() or "chat.openai" in url.lower():
                        ui_name = "ChatGPT"
                    elif "claude.ai" in url.lower():
                        ui_name = "Claude"
                    elif "poe.com" in url.lower():
                        ui_name = "Poe"
                    elif "huggingface" in url.lower():
                        ui_name = "HuggingFace Chat"
                    elif "perplexity" in url.lower():
                        ui_name = "Perplexity"
                    elif "bing" in url.lower() or "copilot" in url.lower():
                        ui_name = "Microsoft Copilot"
                    
                    return DetectionResult(
                        success=True,
                        agent_type="web_ui",
                        endpoint=url,
                        config={
                            "protocol": "browser",
                            "endpoint": url,
                            "ui_name": ui_name,
                            "requires_browser": True,
                            "requires_login": True,
                        },
                        confidence=0.95,
                        notes=[f"Detected {ui_name} (requires browser automation)"]
                    )
        return None
    
    def _probe_endpoint(self, url: str, hints: Dict, notes: List) -> DetectionResult:
        """Probe the endpoint to detect its type."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Try to get the main page
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            notes.append(f"GET {url}: {response.status_code}")
        except Exception as e:
            notes.append(f"Failed to reach {url}: {e}")
            return DetectionResult(
                success=False,
                agent_type="unknown",
                endpoint=url,
                config={},
                confidence=0.0,
                notes=notes
            )
        
        # Check response headers
        content_type = response.headers.get("Content-Type", "")
        server = response.headers.get("Server", "")

        # Check for JSON API
        if "application/json" in content_type:
            return self._analyze_json_api(url, response, hints, notes)

        # Try common API endpoints FIRST before checking HTML UI
        # This allows detecting REST+WebSocket APIs that also serve HTML frontends
        api_result = self._try_common_endpoints(base_url, hints, notes)
        if api_result.success and api_result.confidence > 0.5:
            return api_result

        # Check for HTML (Web UI) as fallback
        if "text/html" in content_type:
            return self._analyze_html_ui(url, base_url, response, hints, notes)

        # Return API result even if low confidence
        return api_result
    
    def _analyze_json_api(self, url: str, response, hints: Dict, notes: List) -> DetectionResult:
        """Analyze a JSON API response."""
        try:
            data = response.json()
            notes.append(f"JSON response keys: {list(data.keys())[:5]}")
            
            # Check for OpenAPI/Swagger
            if "openapi" in data or "swagger" in data:
                return self._parse_openapi(url, data, notes)
            
            # Check for model list (OpenAI-style)
            if "data" in data and isinstance(data["data"], list):
                if any("id" in item for item in data["data"][:3]):
                    notes.append("Detected model list response")
                    return DetectionResult(
                        success=True,
                        agent_type="openai_api",
                        endpoint=url.rsplit("/", 1)[0] + "/chat/completions",
                        config=self._get_default_config("openai_api", url),
                        confidence=0.8,
                        notes=notes
                    )
        except:
            pass
        
        return DetectionResult(
            success=True,
            agent_type="json_api",
            endpoint=url,
            config={"method": "POST", "content_type": "application/json"},
            confidence=0.5,
            notes=notes
        )
    
    def _analyze_html_ui(self, url: str, base_url: str, response, hints: Dict, notes: List) -> DetectionResult:
        """Analyze an HTML page for chat UI patterns."""
        html = response.text.lower()
        
        # Check for framework signatures
        for framework, signatures in self.FRAMEWORK_SIGNATURES.items():
            for sig in signatures:
                if sig.lower() in html:
                    notes.append(f"Detected {framework} signature: {sig}")
                    return DetectionResult(
                        success=True,
                        agent_type=framework,
                        endpoint=url,
                        config=self._get_framework_config(framework, url, base_url),
                        confidence=0.85,
                        notes=notes
                    )
        
        # Check for generic chat UI elements
        chat_indicators = [
            "chat", "message", "send", "input", "conversation",
            "assistant", "bot", "ai", "llm"
        ]
        
        found = [ind for ind in chat_indicators if ind in html]
        if len(found) >= 3:
            notes.append(f"Found chat indicators: {found[:5]}")
            return DetectionResult(
                success=True,
                agent_type="web_ui",
                endpoint=url,
                config={"requires_browser": True},
                confidence=0.6,
                notes=notes
            )
        
        return DetectionResult(
            success=False,
            agent_type="unknown",
            endpoint=url,
            config={},
            confidence=0.2,
            notes=notes + ["Could not identify chat interface"]
        )
    
    def _try_common_endpoints(self, base_url: str, hints: Dict, notes: List) -> DetectionResult:
        """Try common API endpoints."""
        common_paths = [
            "/v1/chat/completions",
            "/v1/models",
            "/api/chat",
            "/api/generate",
            "/api/v1/chat",
            "/api/sessions",  # REST+WebSocket pattern
            "/api/ws",        # REST+WebSocket pattern
            "/chat",
            "/docs",
            "/openapi.json",
        ]

        found_endpoints = {}

        for path in common_paths:
            try:
                test_url = urljoin(base_url, path)
                resp = self.session.get(test_url, timeout=5)

                if resp.status_code in (200, 405, 422):  # 405=Method Not Allowed (POST only), 422=Validation Error
                    found_endpoints[path] = resp.status_code
                    notes.append(f"Found endpoint: {path} ({resp.status_code})")

            except:
                continue

        # Check for REST+WebSocket pattern (sessions + websocket endpoints)
        if "/api/sessions" in found_endpoints or "/api/ws" in found_endpoints:
            notes.append("Detected REST+WebSocket API pattern")
            return DetectionResult(
                success=True,
                agent_type="rest_websocket_api",
                endpoint=base_url,
                config={
                    "protocol": "rest_websocket",
                    "base_url": base_url,
                    "session_endpoint": "/api/sessions",
                    "ws_endpoint_pattern": "/api/ws",  # Will be discovered dynamically
                },
                confidence=0.85,
                notes=notes
            )

        # Check for standard API patterns
        if "/v1/chat/completions" in found_endpoints or "/v1/models" in found_endpoints:
            return DetectionResult(
                success=True,
                agent_type="openai_api",
                endpoint=urljoin(base_url, "/v1/chat/completions"),
                config=self._get_default_config("openai_api", base_url),
                confidence=0.8,
                notes=notes
            )

        if "/api/chat" in found_endpoints or "/api/generate" in found_endpoints:
            return DetectionResult(
                success=True,
                agent_type="ollama",
                endpoint=urljoin(base_url, "/api/chat"),
                config=self._get_default_config("ollama", base_url),
                confidence=0.8,
                notes=notes
            )

        if "/openapi.json" in found_endpoints or "/docs" in found_endpoints:
            notes.append("Found API documentation endpoint")

        return DetectionResult(
            success=False,
            agent_type="unknown",
            endpoint=base_url,
            config={},
            confidence=0.1,
            notes=notes + ["No known endpoints found"]
        )
    
    def _detect_websocket(self, url: str, hints: Dict, notes: List) -> DetectionResult:
        """Handle WebSocket URLs."""
        return DetectionResult(
            success=True,
            agent_type="websocket",
            endpoint=url,
            config={
                "protocol": "websocket",
                "message_format": hints.get("message_format", "json"),
            },
            confidence=0.9,
            notes=notes + ["WebSocket URL detected"]
        )
    
    def _create_config_from_hint(self, url: str, hints: Dict) -> DetectionResult:
        """Create config based on user hints."""
        agent_type = hints["type"]
        config = self._get_default_config(agent_type, url)
        config.update({k: v for k, v in hints.items() if k != "type"})
        
        return DetectionResult(
            success=True,
            agent_type=agent_type,
            endpoint=url,
            config=config,
            confidence=1.0,
            notes=["Configured from user hints"]
        )
    
    def _get_default_config(self, agent_type: str, url: str) -> Dict[str, Any]:
        """Get default configuration for an agent type."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        configs = {
            "openai_api": {
                "protocol": "http",
                "method": "POST",
                "endpoint": urljoin(base_url, "/v1/chat/completions"),
                "format": "openai",
                "headers": {"Content-Type": "application/json"},
            },
            "anthropic_api": {
                "protocol": "http",
                "method": "POST",
                "endpoint": urljoin(base_url, "/v1/messages"),
                "format": "anthropic",
                "headers": {
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
            },
            "ollama": {
                "protocol": "http",
                "method": "POST",
                "endpoint": urljoin(base_url, "/api/chat"),
                "format": "ollama",
                "headers": {"Content-Type": "application/json"},
            },
            "websocket": {
                "protocol": "websocket",
                "endpoint": url,
            },
            "gradio": {
                "protocol": "gradio",
                "endpoint": url,
                "use_gradio_client": True,
            },
            "streamlit": {
                "protocol": "streamlit",
                "endpoint": url,
                "requires_browser": True,
            },
        }
        
        return configs.get(agent_type, {"endpoint": url})
    
    def _get_framework_config(self, framework: str, url: str, base_url: str) -> Dict[str, Any]:
        """Get configuration for a detected framework."""
        if framework == "gradio":
            return {
                "protocol": "gradio",
                "endpoint": url,
                "api_endpoint": urljoin(base_url, "/api/predict"),
                "use_gradio_client": True,
            }
        elif framework == "streamlit":
            return {
                "protocol": "streamlit",
                "endpoint": url,
                "requires_browser": True,
            }
        elif framework == "chainlit":
            return {
                "protocol": "chainlit",
                "endpoint": url,
                "ws_endpoint": url.replace("http", "ws") + "/ws",
            }
        return {"endpoint": url}
    
    def _parse_openapi(self, url: str, spec: Dict, notes: List) -> DetectionResult:
        """Parse OpenAPI specification."""
        notes.append("Found OpenAPI specification")
        
        # Find chat/completion endpoints
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            if "chat" in path.lower() or "completion" in path.lower():
                return DetectionResult(
                    success=True,
                    agent_type="openai_api",
                    endpoint=urljoin(url, path),
                    config=self._get_default_config("openai_api", url),
                    confidence=0.95,
                    notes=notes + [f"Found chat endpoint: {path}"]
                )
        
        return DetectionResult(
            success=True,
            agent_type="json_api",
            endpoint=url,
            config={"openapi_spec": spec},
            confidence=0.7,
            notes=notes
        )


def detect_agent(url: str, hints: Dict = None) -> DetectionResult:
    """Convenience function to detect agent type."""
    detector = AgentDetector()
    return detector.detect(url, hints)


# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python detect_agent.py <url> [hints_json]")
        print("\nExamples:")
        print("  python detect_agent.py http://localhost:11434")
        print("  python detect_agent.py http://localhost:7860 '{\"type\": \"gradio\"}'")
        sys.exit(1)
    
    url = sys.argv[1]
    hints = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print(f"🔍 Analyzing: {url}\n")
    
    result = detect_agent(url, hints)
    
    print(f"{'✅' if result.success else '❌'} Detection {'successful' if result.success else 'failed'}")
    print(f"Type: {result.agent_type}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Endpoint: {result.endpoint}")
    print(f"\nNotes:")
    for note in result.notes:
        print(f"  - {note}")
    print(f"\nConfig:")
    print(json.dumps(result.config, indent=2))
