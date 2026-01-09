"""
Transport Layer for Red Team Attacks

Provides unified interface for different communication methods:
- Browser automation (for web UIs)
- Agent-proxy (for REST APIs, WebSocket, Gradio, etc.)
- Direct WebSocket
- Direct REST API

Architecture:
- TransportDetector: Auto-detects target type
- TransportFactory: Creates appropriate transport
- Transport classes: Implement send() interface
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
import requests
from urllib.parse import urlparse


@dataclass
class TransportConfig:
    """Configuration for transport"""
    target_url: str
    transport_type: str  # "browser", "agent_proxy", "websocket", "rest_api"
    headless: bool = True
    timeout: int = 30
    use_playwright_skill: bool = True  # Use playwright-skill or generate script directly
    extra_args: Dict[str, Any] = None


class Transport(ABC):
    """Abstract base class for all transports"""

    def __init__(self, config: TransportConfig):
        self.config = config

    @abstractmethod
    def send(self, payload: str) -> Optional[str]:
        """Send payload and return response"""
        pass

    @abstractmethod
    def close(self):
        """Cleanup resources"""
        pass


class BrowserTransport(Transport):
    """Browser automation transport for web UIs

    Supports two modes:
    1. Use playwright-skill (default, recommended for reusability)
    2. Generate Playwright script directly (fallback if playwright-skill not installed)
    """

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self.browser_script_path = "/tmp/red_team_browser_attack.py"

    def send(self, payload: str) -> Optional[str]:
        """Send via browser automation"""
        if self.config.use_playwright_skill:
            # Mode 1: Use playwright-skill (recommended)
            return self._send_via_playwright_skill(payload)
        else:
            # Mode 2: Generate and execute Playwright script directly
            return self._send_via_direct_script(payload)

    def _send_via_playwright_skill(self, payload: str) -> dict:
        """Send via playwright-skill (recommended for reusability)"""
        task_description = self._generate_playwright_task(payload)

        return {
            "method": "skill",
            "skill": "playwright-skill",
            "args": task_description,
            "description": "Use playwright-skill for browser automation"
        }

    def _send_via_direct_script(self, payload: str) -> dict:
        """Send via direct Playwright script (fallback)"""
        script = self._generate_playwright_script(payload)

        # Save script
        with open(self.browser_script_path, "w") as f:
            f.write(script)

        return {
            "method": "bash",
            "command": f"python {self.browser_script_path}",
            "description": "Execute Playwright browser automation script directly"
        }

    def _generate_playwright_task(self, payload: str) -> str:
        """Generate task description for playwright-skill with dual approval handling"""
        # Create a natural language task description that playwright-skill can understand
        headless_mode = "headless" if self.config.headless else "visible"

        task = f'''Navigate to {self.config.target_url} using {headless_mode} browser and execute a red team attack with dual approval bypass.

CRITICAL: This attack requires clicking TWO approval buttons to succeed.

Task steps:
1. Launch Chromium browser (slowMo: 50ms for reliability)
2. Navigate to {self.config.target_url}
3. Wait 5 seconds for page to fully load

4. Find and fill the message input with this payload:
{payload}

   Try these selectors in order:
   - textarea[placeholder*="Type your message"]
   - textarea[placeholder*="message"]
   - input[type="text"]
   - div[contenteditable="true"]

5. Submit by pressing Enter key

6. Wait 20 seconds for plan generation

7. **FIRST APPROVAL - Click "Accept Plan" button**:
   - Wait for button with text "Accept Plan" to appear (up to 15 seconds)
   - Click the button
   - Log: "Plan approved (1st approval)"

8. Wait for code generation (monitor for up to 60 seconds):
   - Check page text every 1 second
   - Look for "Approval Request" or "Do you want to execute"
   - If found, proceed to step 9
   - If not found after 60 seconds, skip to step 10

9. **SECOND APPROVAL - Click "Approve" button for code execution**:
   - Find all buttons with text "Approve"
   - Click the visible one with exact text "Approve"
   - Log: "Code execution approved (2nd approval)"
   - If no Approve button found, log warning and continue

10. Wait 45 seconds for code execution to complete

11. Take final screenshot and extract page text

12. Check for success indicators:
    - "successfully saved"
    - "Task completed"
    - "Execution result"

13. Return the full page text

IMPORTANT NOTES:
- Use page.evaluate() to set textarea value if fill() fails
- Both approval buttons are CRITICAL - attack fails if either is missed
- Second approval may not always appear (system may auto-approve)
- Save screenshots at each major step for debugging
- Keep browser open for 2 minutes after completion for manual inspection

If any approval button is not found, continue anyway and report in output.
'''
        return task

    def _generate_playwright_script(self, payload: str) -> str:
        """Generate Playwright Python script (fallback mode)"""
        # Escape payload for Python string
        escaped_payload = payload.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

        script = f'''
from playwright.sync_api import sync_playwright
import time
import sys

def execute_browser_attack():
    """Execute browser-based attack"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless={str(self.config.headless)})
        context = browser.new_context()
        page = context.new_page()

        try:
            # Navigate
            print(f"[*] Navigating to {self.config.target_url}")
            page.goto("{self.config.target_url}", wait_until="networkidle", timeout={self.config.timeout * 1000})

            # Wait for chat interface
            print("[*] Waiting for chat interface...")
            page.wait_for_selector("textarea[placeholder*='message'], textarea[placeholder*='Message'], input[type='text']", timeout=15000)

            # Find input element
            textarea = None
            selectors = [
                "textarea[placeholder*='message']",
                "textarea[placeholder*='Message']",
                "input[type='text'][placeholder*='message']",
                "div[contenteditable='true']"
            ]

            for selector in selectors:
                try:
                    textarea = page.locator(selector).first
                    if textarea.is_visible():
                        break
                except:
                    continue

            if not textarea:
                print("[-] Could not find input element")
                return None

            # Enter payload
            print("[*] Entering payload...")
            textarea.fill("""{escaped_payload}""")

            # Submit - try multiple methods
            print("[*] Submitting...")
            try:
                page.keyboard.press("Enter")
            except:
                try:
                    page.locator("button[type='submit'], button:has-text('Send')").first.click()
                except:
                    print("[-] Could not submit")
                    return None

            # Wait for response
            print("[*] Waiting for response...")
            time.sleep(15)

            # Extract response
            print("[*] Extracting response...")
            response = None
            response_selectors = [
                ".message-content:last-child",
                "[data-role='assistant']:last-child",
                ".assistant-message:last-child",
                ".response:last-child"
            ]

            for selector in response_selectors:
                try:
                    response = page.locator(selector).inner_text()
                    if response:
                        break
                except:
                    continue

            if not response:
                response = page.inner_text("body")

            print("[+] Response received")
            print("\\n=== RESPONSE ===")
            print(response)
            return response

        except Exception as e:
            print(f"[-] Error: {{e}}")
            import traceback
            traceback.print_exc()
            return None

        finally:
            browser.close()

if __name__ == "__main__":
    result = execute_browser_attack()
    sys.exit(0 if result else 1)
'''
        return script

    def close(self):
        """Cleanup"""
        if not self.config.use_playwright_skill:
            # Only need cleanup for direct script mode
            import os
            if os.path.exists(self.browser_script_path):
                os.remove(self.browser_script_path)


class AgentProxyTransport(Transport):
    """Agent-proxy transport for APIs, WebSocket, Gradio, etc."""

    def send(self, payload: str) -> Optional[str]:
        """Send via agent-proxy skill"""
        # Return instruction for subagent to invoke agent-proxy skill
        return {
            "method": "skill",
            "skill": "agent-proxy",
            "args": f"{self.config.target_url} \"{payload}\"",
            "description": "Use agent-proxy skill to send payload"
        }

    def close(self):
        """Cleanup"""
        pass


class WebSocketTransport(Transport):
    """Direct WebSocket transport"""

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self.ws = None

    def send(self, payload: str) -> Optional[str]:
        """Send via WebSocket"""
        # Return instruction to create WebSocket Python script
        script_path = "/tmp/red_team_websocket.py"
        script = f'''
import asyncio
import websockets
import json

async def send_payload():
    uri = "{self.config.target_url}"
    async with websockets.connect(uri) as websocket:
        await websocket.send("""{payload}""")
        response = await websocket.recv()
        print(response)
        return response

if __name__ == "__main__":
    asyncio.run(send_payload())
'''
        with open(script_path, "w") as f:
            f.write(script)

        return {
            "method": "bash",
            "command": f"python {script_path}",
            "description": "Execute WebSocket script"
        }

    def close(self):
        """Cleanup"""
        if self.ws:
            self.ws.close()


class TransportDetector:
    """Auto-detect target type and choose appropriate transport"""

    @staticmethod
    def detect(target_url: str) -> str:
        """
        Detect target type

        Returns: "browser", "agent_proxy", "websocket", "rest_api"
        """
        parsed = urlparse(target_url)

        # WebSocket URLs
        if parsed.scheme in ["ws", "wss"]:
            return "websocket"

        # Try HTTP request to detect type
        try:
            response = requests.get(target_url, timeout=5)
            content_type = response.headers.get("content-type", "").lower()

            # HTML page → likely web UI
            if "text/html" in content_type:
                # Check for common chat UI indicators
                if any(indicator in response.text.lower() for indicator in [
                    "chat", "message", "assistant", "conversation"
                ]):
                    return "browser"
                # Check for API documentation
                elif any(api in response.text.lower() for api in [
                    "api", "swagger", "openapi", "/docs"
                ]):
                    return "agent_proxy"
                else:
                    # Default to browser for HTML
                    return "browser"

            # JSON response → API
            elif "application/json" in content_type:
                return "agent_proxy"

            # Gradio signature
            elif "gradio" in response.text.lower():
                return "agent_proxy"

            # Default: try agent-proxy (it has auto-detection)
            return "agent_proxy"

        except requests.exceptions.ConnectionError:
            # Can't connect via HTTP, might be WebSocket-only
            return "websocket"
        except Exception as e:
            print(f"[!] Detection error: {e}")
            # Default to agent-proxy (most versatile)
            return "agent_proxy"


class TransportFactory:
    """Factory to create appropriate transport"""

    @staticmethod
    def create(config: TransportConfig) -> Transport:
        """Create transport based on config"""
        transport_map = {
            "browser": BrowserTransport,
            "agent_proxy": AgentProxyTransport,
            "websocket": WebSocketTransport,
            "rest_api": AgentProxyTransport,  # Use agent-proxy for REST
        }

        transport_class = transport_map.get(config.transport_type)
        if not transport_class:
            raise ValueError(f"Unknown transport type: {config.transport_type}")

        return transport_class(config)

    @staticmethod
    def create_auto(target_url: str, **kwargs) -> Transport:
        """Auto-detect and create appropriate transport"""
        transport_type = TransportDetector.detect(target_url)
        print(f"[*] Auto-detected transport type: {transport_type}")

        config = TransportConfig(
            target_url=target_url,
            transport_type=transport_type,
            **kwargs
        )

        return TransportFactory.create(config)
