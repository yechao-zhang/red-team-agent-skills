#!/usr/bin/env python3
"""
Browser Automation Adapter

Uses Playwright to interact with web-based chat UIs like:
- Gemini (gemini.google.com)
- ChatGPT (chat.openai.com)
- Claude (claude.ai)
- Any web chat interface

Requires: pip install playwright && playwright install
"""

import time
import re
import logging # Import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__) # Initialize logger

@dataclass
class WebUIConfig:
    """Configuration for a known web UI."""
    name: str
    url_pattern: str
    input_selector: str  # CSS selector for input textarea/field
    submit_selector: str  # CSS selector for submit button (or None if Enter works)
    response_selector: str  # CSS selector for response container
    wait_for_response: str  # Selector to wait for to know response is complete
    login_required: bool = True
    extra_wait: float = 1.0  # Extra wait time after response detected


# Known web UI configurations
KNOWN_WEB_UIS: Dict[str, WebUIConfig] = {
    "gemini": WebUIConfig(
        name="Google Gemini",
        url_pattern=r"gemini\.google\.com",
        input_selector='div[contenteditable="true"], rich-textarea textarea, textarea[aria-label*="prompt"], .ql-editor, textarea',
        submit_selector='button[aria-label*="Send"], button[data-test-id="send-button"], button.send-button, button[type="submit"]',
        response_selector='message-content, model-response, .response-container',
        wait_for_response='message-content, model-response, .response-container',
        login_required=True,
        extra_wait=3.0,
    ),
    "chatgpt": WebUIConfig(
        name="ChatGPT",
        url_pattern=r"chat\.openai\.com|chatgpt\.com",
        input_selector='textarea[data-id="root"], #prompt-textarea, textarea[placeholder*="Message"]',
        submit_selector='button[data-testid="send-button"], button[aria-label="Send prompt"]',
        response_selector='[data-message-author-role="assistant"] .markdown',
        wait_for_response='[data-message-author-role="assistant"]',
        login_required=True,
        extra_wait=2.0,
    ),
    "claude": WebUIConfig(
        name="Claude",
        url_pattern=r"claude\.ai",
        input_selector='div[contenteditable="true"], textarea[placeholder*="message"], .ProseMirror',
        submit_selector='button[aria-label="Send Message"], button[type="submit"]',
        response_selector='[data-is-streaming], .claude-response, .assistant-message',
        wait_for_response='[data-is-streaming="false"], .assistant-message',
        login_required=True,
        extra_wait=2.0,
    ),
    "poe": WebUIConfig(
        name="Poe",
        url_pattern=r"poe\.com",
        input_selector='textarea[class*="GrowingTextArea"], textarea[placeholder*="message"]',
        submit_selector='button[class*="SendButton"]',
        response_selector='[class*="Message_botMessageBubble"]',
        wait_for_response='[class*="Message_botMessageBubble"]',
        login_required=True,
        extra_wait=1.5,
    ),
    "huggingface_chat": WebUIConfig(
        name="HuggingFace Chat",
        url_pattern=r"huggingface\.co/chat",
        input_selector='textarea[placeholder*="message"], textarea[enterkeyhint="send"]',
        submit_selector='button[type="submit"]',
        response_selector='.prose.dark\\:prose-invert',
        wait_for_response='.prose',
        login_required=False,
        extra_wait=2.0,
    ),
    # Add Magentic-UI configuration
    "magentic_ui": WebUIConfig(
        name="Magentic-UI",
        url_pattern=r"localhost:8082", # Assuming it runs on localhost:8082
        input_selector='textarea[placeholder*="message" i], textarea',
        submit_selector='button[aria-label="Submit"], button[type="submit"], button:has-text("Send")',
        response_selector='.message-bubble.assistant, .message-content, .assistant-message',
        wait_for_response='.message-bubble.assistant, .message-content, .assistant-message',
        login_required=False,
        extra_wait=3.0,
    ),
}


class BrowserAdapter:
    """
    Browser automation adapter for web-based chat UIs.
    """
    
    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for browser automation.\n"
                "Install with: pip install playwright && playwright install chromium"
            )
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.config: Optional[WebUIConfig] = None
        self.custom_config: Dict[str, Any] = {}
        self.conversation_history: List[Dict[str, str]] = []
        self.logger = logging.getLogger(__name__) # Use specific logger


    def connect(self, url: str, config: Dict[str, Any] = None) -> str:
        """
        Connect to a web UI.
        
        Args:
            url: The web UI URL
            config: Optional configuration overrides:
                - headless: bool (default True if user_data_dir provided, else False)
                - user_data_dir: str (for persistent login)
                - input_selector: str (override auto-detect)
                - submit_selector: str
                - response_selector: str
        
        Returns:
            Status message
        """
        config = config or {}
        self.custom_config = config
        
        # Detect which UI this is
        self.config = self._detect_web_ui(url)
        if not self.config:
            self.logger.warning(f"Could not auto-detect web UI for {url}. Using generic selectors.")
            self.config = WebUIConfig(
                name="Generic Web UI",
                url_pattern=url,
                input_selector=config.get("input_selector", 'textarea[placeholder*="message" i], div[contenteditable="true"]'),
                submit_selector=config.get("submit_selector", 'button[type="submit"], button[aria-label*="send" i]'),
                response_selector=config.get("response_selector", '.message-bubble.assistant, .response-container'),
                wait_for_response=config.get("response_selector", '.message-bubble.assistant, .response-container'),
                login_required=False,
                extra_wait=2.0,
            )

        self.logger.info(f"Connecting to {self.config.name} at {url}")

        # Start browser
        self.playwright = sync_playwright().start()
        
        # Use persistent context if user_data_dir provided (keeps login)
        user_data_dir = config.get("user_data_dir")
        
        # If we have a saved profile, default to headless (already logged in)
        # Otherwise, show browser for manual login
        headless = config.get("headless")
        if headless is None:
            headless = bool(user_data_dir)  # Auto: headless if profile exists
        
        # Use system Chrome instead of Chromium to avoid Google's bot detection
        use_chrome = config.get("use_chrome", True)  # Default to Chrome
        channel = "chrome" if use_chrome else None

        # Anti-detection arguments
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        
        # Add slow_mo for debugging visible browser
        slow_mo = config.get("slow_mo", 100) if not headless else 0


        if user_data_dir:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=headless,
                channel=channel,
                viewport={"width": 1280, "height": 800},
                args=browser_args,
                ignore_default_args=["--enable-automation"],
                slow_mo=slow_mo,
            )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        else:
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                channel=channel,
                args=browser_args,
                ignore_default_args=["--enable-automation"],
                slow_mo=slow_mo,
            )
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            self.page = self.context.new_page()

        # Remove webdriver property to avoid detection
        if self.page:
            self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
        
        # Navigate to URL (use domcontentloaded for dynamic SPAs like Gemini)
        self.logger.info(f"Navigating to {url}...")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_load_state("networkidle") # Wait for network to settle
        
        # Wait a bit for dynamic content
        time.sleep(2)
        
        ui_name = self.config.name
        
        # Check if already logged in
        is_logged_in = self._check_if_logged_in()
        
        if is_logged_in:
            return f"✅ Connected to {ui_name} (already logged in)"
        elif user_data_dir and self.config.login_required:
            return f"⚠️ Connected to {ui_name}, but login may be required. Use wait_for_login() if needed."
        else:
            return f"✅ Connected to {ui_name}. No login required or already logged in."
    
    def _check_if_logged_in(self) -> bool:
        """Check if user is already logged in by looking for input field."""
        if not self.page:
            return False
        
        input_selector = self.custom_config.get("input_selector") or \
                        (self.config.input_selector if self.config else "textarea")
        
        # Try to find an editable input. If found, assume logged in.
        try:
            elem = self.page.query_selector(input_selector)
            if elem and elem.is_visible() and elem.is_editable():
                return True
        except PlaywrightTimeoutError:
            pass # Selector not found, not logged in
        
        return False
    
    def _detect_web_ui(self, url: str) -> Optional[WebUIConfig]:
        """Detect which known web UI this is, or auto-detect for unknown sites."""
        # First, check known UIs
        for key, config in KNOWN_WEB_UIS.items():
            if re.search(config.url_pattern, url, re.IGNORECASE):
                self.logger.info(f"Detected known Web UI: {config.name}")
                return config

        # For unknown UIs, try auto-detection
        self.logger.info(f"No known Web UI detected for {url}. Attempting auto-detection.")
        return self._auto_detect_chat_ui()

    def _auto_detect_chat_ui(self) -> Optional[WebUIConfig]:
        """
        Auto-detect chat UI elements for unknown websites.
        Returns a WebUIConfig with detected selectors.
        """
        if not self.page:
            return None

        detected = {
            "input_selector": None,
            "submit_selector": None,
            "response_selector": None,
        }

        # Common input patterns (priority order)
        input_candidates = [
            'textarea[placeholder*="message" i]',
            'textarea[placeholder*="chat" i]',
            'textarea[placeholder*="ask" i]',
            'textarea[placeholder*="type" i]',
            'div[contenteditable="true"]',
            'textarea:not([readonly])',
            'input[type="text"][placeholder*="message" i]',
        ]

        for sel in input_candidates:
            try:
                elem = self.page.query_selector(sel)
                if elem and elem.is_visible() and elem.is_editable():
                    detected["input_selector"] = sel
                    self.logger.debug(f"Auto-detected input selector: {sel}")
                    break
            except:
                pass

        # Common submit button patterns
        submit_candidates = [
            'button[type="submit"]',
            'button[aria-label*="send" i]',
            'button[aria-label*="submit" i]',
            'button:has-text("Send")',
            'button:has-text("Submit")',
            'button:has(svg)',  # Icon button near input
            'button:has-text("Run")', # For Magentic-UI
            'button:has-text("开始")', # For Magentic-UI
        ]

        for sel in submit_candidates:
            try:
                elem = self.page.query_selector(sel)
                if elem and elem.is_visible() and elem.is_enabled():
                    detected["submit_selector"] = sel
                    self.logger.debug(f"Auto-detected submit selector: {sel}")
                    break
            except:
                pass

        # Common response container patterns
        response_candidates = [
            '.message-bubble.assistant', # For Magentic-UI
            '[class*="message" i][class*="bot" i]',
            '[class*="message" i][class*="assistant" i]',
            '[class*="response" i]',
            '[class*="answer" i]',
            '[class*="reply" i]',
            '[data-role="assistant"]',
            '[data-message-author-role="assistant"]',
        ]

        for sel in response_candidates:
            try:
                elems = self.page.query_selector_all(sel)
                if elems:
                    detected["response_selector"] = sel
                    self.logger.debug(f"Auto-detected response selector: {sel}")
                    break
            except:
                pass

        # If we found at least input, create a config
        if detected["input_selector"]:
            return WebUIConfig(
                name="Auto-detected Chat UI",
                url_pattern=".*",  # Match any
                input_selector=detected["input_selector"],
                submit_selector=detected["submit_selector"] or 'button[type="submit"]',
                response_selector=detected["response_selector"] or '.message-bubble.assistant, .response-container',
                wait_for_response=detected["response_selector"] or '.message-bubble.assistant, .response-container',
                login_required=False,
                extra_wait=3.0,
            )

        return None
    
    def wait_for_login(self, timeout: int = 300) -> str:
        """
        Wait for user to complete login.
        If already logged in, returns immediately.
        
        Args:
            timeout: Max seconds to wait
        
        Returns:
            Status message
        """
        if not self.page:
            raise RuntimeError("Not connected")
        
        # Check if already logged in
        if self._check_if_logged_in():
            self.logger.info("Already logged in, ready to chat!")
            return "✅ Already logged in, ready to chat!"
        
        self.logger.info(f"Waiting for login (up to {timeout}s)... Please login in the browser window.")
        
        # Wait for input field to appear (indicates logged in)
        input_selector = self.custom_config.get("input_selector") or \
                        (self.config.input_selector if self.config else "textarea")
        
        try:
            self.page.wait_for_selector(input_selector, timeout=timeout * 1000)
            self.logger.info("Login detected, ready to chat!")
            return "✅ Login detected, ready to chat!"
        except PlaywrightTimeoutError:
            self.logger.warning("Login timeout. You may need to login manually.")
            return "⚠️ Login timeout. You may need to login manually."
        except Exception as e:
            self.logger.error(f"Error while waiting for login: {e}")
            return f"❌ Error during login wait: {e}"
    
    def send_message(self, message: str) -> str:
        """
        Send a message and get the response.
        
        Args:
            message: The message to send
            
        Returns:
            The assistant's response
        """
        if not self.page:
            raise RuntimeError("Not connected. Call connect() first.")
        
        self.logger.info(f"Sending message: '{message[:50]}...'")

        # Get selectors
        input_sel = self.custom_config.get("input_selector") or \
                   (self.config.input_selector if self.config else "textarea")
        submit_sel = self.custom_config.get("submit_selector") or \
                    (self.config.submit_selector if self.config else None)
        response_sel = self.custom_config.get("response_selector") or \
                      (self.config.response_selector if self.config else ".response")
        extra_wait = self.config.extra_wait
        
        # Count existing responses to detect new one
        existing_responses = self.page.query_selector_all(response_sel)
        initial_count = len(existing_responses)
        
        # Find and fill input
        input_elem = self._find_input_element(input_sel)
        if not input_elem:
            self.logger.error(f"Could not find input element: {input_sel}")
            # Take screenshot before raising error
            self.screenshot(f"debug_no_input_{time.time()}.png")
            raise RuntimeError(f"Could not find input element: {input_sel}")
        
        # Clear and type message
        self.logger.debug("Typing message...")
        self._type_message(input_elem, message)
        
        # Submit
        self.logger.debug("Submitting message...")
        self._submit_message(submit_sel)
        
        # Wait for response and handle approval buttons DURING the wait
        response = self._wait_for_response_and_approval(response_sel, initial_count, extra_wait)
        
        # Record in history
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": response})
        
        self.logger.info(f"Received response: '{response[:50]}...'")
        return response
    
    def _find_input_element(self, selector: str):
        """Find the input element, trying multiple selectors."""
        selectors = selector.split(", ")
        
        for sel in selectors:
            try:
                self.logger.debug(f"Trying input selector: {sel}")
                elem = self.page.wait_for_selector(sel.strip(), timeout=5000)
                if elem and elem.is_visible() and elem.is_editable():
                    self.logger.debug(f"Found editable input: {sel}")
                    return elem
            except PlaywrightTimeoutError:
                self.logger.debug(f"Input selector {sel} not found or not editable within timeout.")
                continue
            except Exception as e:
                self.logger.debug(f"Error with input selector {sel}: {e}")
        
        return None
    
    def _type_message(self, input_elem, message: str):
        """Type message into the input element."""
        try:
            self.logger.debug("Clicking input element.")
            input_elem.click()
            time.sleep(0.3)
            
            self.logger.debug("Clearing existing content.")
            self.page.keyboard.press("Control+a")
            time.sleep(0.1)
            
            self.logger.debug("Filling message.")
            input_elem.fill(message)
            time.sleep(0.5) # Give UI time to register fill
        except Exception as e:
            self.logger.error(f"Error filling input element: {e}. Trying fallback type.")
            # Fallback: try typing directly if fill fails
            input_elem.click()
            self.page.keyboard.type(message, delay=10)
            time.sleep(0.5)
    
    def _submit_message(self, submit_sel: Optional[str]):
        """Submit the message."""
        submitted = False
        
        # Try submit button first
        if submit_sel:
            selectors = submit_sel.split(", ")
            for sel in selectors:
                try:
                    self.logger.debug(f"Trying submit selector: {sel}")
                    btn = self.page.query_selector(sel.strip())
                    if btn and btn.is_visible() and btn.is_enabled():
                        self.logger.info(f"Clicking submit button: {sel}")
                        btn.click()
                        submitted = True
                        break
                except Exception as e:
                    self.logger.debug(f"Submit selector {sel} failed: {e}")
                    continue
        
        # Fallback to Enter key
        if not submitted:
            self.logger.warning("No submit button found or clicked. Pressing Enter.")
            self.page.keyboard.press("Enter")
        
        time.sleep(1.0) # Give some time for submission to register

    def _wait_for_response_and_approval(self, response_sel: str, initial_count: int, extra_wait: float, timeout: int = 120) -> str:
        """Wait for and extract the response, while also monitoring for approval buttons."""
        start_time = time.time()
        last_response_text = ""
        last_check_time = time.time()
        
        self.logger.info("Waiting for agent response and monitoring for approval buttons...")

        while time.time() - start_time < timeout:
            # Check for approval buttons periodically
            if time.time() - last_check_time > 1.0: # Check every 1 second
                if self._click_approval_button():
                    self.logger.info("Approval button clicked, continuing to monitor response.")
                last_check_time = time.time()

            responses = self.page.query_selector_all(response_sel)
            
            if len(responses) > initial_count:
                # New response appeared, use smart completion detection
                self.logger.debug("New response detected, waiting for completion.")
                last_response_text = self._wait_for_completion(response_sel, start_time, timeout)
                
                # After completion, check for approval buttons one last time
                self._click_approval_button()
                
                # Add extra wait for dynamic UIs
                time.sleep(extra_wait)
                return last_response_text

            time.sleep(0.5)

        self.logger.warning("Response timeout. No new response received within timeout.")
        return last_response_text if last_response_text else "No response received within timeout."

    def _click_approval_button(self) -> bool:
        """Attempts to click a common approval button if one is found and visible and enabled."""
        accept_patterns = [
            'button:has-text("Accept")',
            'button:has-text("Confirm")',
            'button:has-text("Approve")',
            'button:has-text("Yes")',
            'button:has-text("OK")',
            'button:has-text("Allow")',
            'button:has-text("Run")',
            'button:has-text("Execute")',
            'button:has-text("Continue")',
            'button:has-text("允许")',
            'button:has-text("确认")',
            'button:has-text("接受")',
            'button[aria-label*="accept" i]',
            'button[aria-label*="confirm" i]',
            'button[aria-label*="approve" i]',
            'button[type="button"][class*="MuiButton-root"]', # Generic button for frameworks like MUI
        ]

        for pattern in accept_patterns:
            try:
                buttons = self.page.query_selector_all(pattern)
                for button in buttons:
                    if button and button.is_visible() and button.is_enabled():
                        text = button.inner_text() or button.get_attribute("aria-label")
                        self.logger.info(f"Automatically clicking approval button: '{text}' (Pattern: {pattern})")
                        button.click()
                        time.sleep(0.5) # Give UI time to react
                        return True
            except PlaywrightTimeoutError:
                continue # Button not present yet, or disappeared
            except Exception as e:
                self.logger.debug(f"Error while checking/clicking approval button '{pattern}': {e}")
        return False

    def _wait_for_completion(self, response_sel: str, start_time: float, timeout: int) -> str:
        """
        Smart detection for when agent has finished responding.
        Uses multiple signals: text stability, button state, loading indicators.
        """
        last_text = ""
        stable_count = 0
        min_stable_checks = 3  # Require 3 consecutive stable checks for robustness

        self.logger.debug("Monitoring response completion...")

        while time.time() - start_time < timeout:
            time.sleep(1.0) # Check every second

            # Method 1: Check if send button is re-enabled (universal signal)
            send_btn_ready = self._is_send_button_ready()

            # Method 2: Check if loading/typing indicators are gone
            not_loading = self._is_loading_complete()

            # Method 3: Check text stability
            responses = self.page.query_selector_all(response_sel)
            current_text = ""
            if responses:
                current_text = responses[-1].inner_text().strip()

            text_stable = bool(current_text and current_text == last_text)

            self.logger.debug(f"Completion check: stable={text_stable} ({stable_count}), send_ready={send_btn_ready}, not_loading={not_loading}, current_text='{current_text[:50]}...'")

            if text_stable:
                stable_count += 1

                # Strong signal: button ready or not loading
                if stable_count >= min_stable_checks and (send_btn_ready or not_loading):
                    self.logger.info("Response completion detected (stable text + send button ready/no loading).")
                    return current_text

                # Fallback: just text stability for longer time
                if stable_count >= min_stable_checks + 2: # Wait a bit longer for text stability alone
                    self.logger.info("Response completion detected (text stable for extended period).")
                    return current_text
            else:
                stable_count = 0
                last_text = current_text

        self.logger.warning("Response completion timeout. Returning latest text.")
        return last_text if last_text else "Response completion timeout."

    def _is_send_button_ready(self) -> bool:
        """Check if send button is enabled (indicates agent finished)."""
        submit_sel = self.custom_config.get("submit_selector") or \
                    (self.config.submit_selector if self.config else None)

        if not submit_sel:
            return False

        for sel in submit_sel.split(", "):
            try:
                btn = self.page.query_for_selector(sel.strip(), state="attached", timeout=100) # Quick check
                if btn:
                    # Check if button is enabled
                    is_disabled = btn.get_attribute("disabled")
                    aria_disabled = btn.get_attribute("aria-disabled")
                    if not is_disabled and aria_disabled != "true":
                        return True
            except PlaywrightTimeoutError:
                pass # Selector not found quickly
            except Exception as e:
                self.logger.debug(f"Error checking send button {sel}: {e}")
        return False

    def _is_loading_complete(self) -> bool:
        """Check if loading/typing indicators have disappeared."""
        loading_indicators = [
            '[data-is-streaming="true"]',
            '.loading', '.spinner', '.typing',
            '[aria-busy="true"]',
            '.animate-pulse', '.animate-spin',
            '[class*="loading"]', '[class*="typing"]',
            '[class*="streaming"]',
        ]

        for indicator in loading_indicators:
            try:
                elem = self.page.query_selector(indicator)
                if elem and elem.is_visible():
                    return False  # Still loading
            except:
                pass

        return True  # No loading indicators found
    
    def _wait_for_streaming_complete(self, timeout: int = 60):
        """Wait for streaming response to complete."""
        # This function might be redundant with _wait_for_completion,
        # but is kept for specific streaming use cases if needed.
        self.logger.warning("'_wait_for_streaming_complete' called, consider integrating into _wait_for_completion.")
        time.sleep(self.config.extra_wait) # Use the extra wait from config
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history
    
    def reset(self):
        """Reset conversation (may need to refresh page)."""
        self.conversation_history = []
        if self.page:
            self.page.reload()
            time.sleep(self.config.extra_wait) # Wait after reload
        self.logger.info("Conversation reset.")
    
    def screenshot(self, path: str):
        """Take a screenshot for debugging."""
        if self.page:
            try:
                self.page.screenshot(path=path)
                self.logger.info(f"Screenshot saved to {path}")
            except PlaywrightTimeoutError:
                self.logger.warning(f"Screenshot timeout for {path}")
            except Exception as e:
                self.logger.error(f"Error taking screenshot to {path}: {e}")
    
    def close(self):
        """Close the browser."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self.logger.info("Browser closed.")


class WebUIProxy:
    """
    High-level proxy for web UI chat interfaces.
    
    Usage:
        proxy = WebUIProxy()
        proxy.connect("https://gemini.google.com")
        proxy.wait_for_login()  # Wait for user to login
        
        response = proxy.say("Hello!")
        response = proxy.say("Tell me more")
        
        proxy.close()
    """
    
    def __init__(self):
        self.adapter = BrowserAdapter()
        self._connected = False
        self.logger = logging.getLogger(__name__) # Use specific logger
    
    def connect(self, url: str, headless: bool = False, user_data_dir: str = None) -> str:
        """
        Connect to a web UI.
        
        Args:
            url: The chat UI URL
            headless: Run browser in headless mode (default False for login)
            user_data_dir: Directory to store browser profile (keeps login state)
        
        Returns:
            Status message
        """
        config = {
            "headless": headless,
        }
        if user_data_dir:
            config["user_data_dir"] = user_data_dir
        
        result = self.adapter.connect(url, config)
        self._connected = True
        self.logger.info(f"WebUIProxy connected status: {result}")
        return result
    
    def wait_for_login(self, timeout: int = 300) -> str:
        """Wait for login to complete."""
        result = self.adapter.wait_for_login(timeout)
        self.logger.info(f"Login status: {result}")
        return result
    
    def say(self, message: str) -> str:
        """Send a message and get response."""
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        self.logger.info(f"WebUIProxy sending message: '{message[:50]}...'")
        response = self.adapter.send_message(message)
        self.logger.info(f"WebUIProxy received response: '{response[:50]}...'")
        return response
    
    @property
    def history(self) -> List[Dict[str, str]]:
        """Get conversation history."""
        return self.adapter.get_history()
    
    def screenshot(self, path: str = "debug_screenshot.png"):
        """Take a screenshot for debugging."""
        self.adapter.screenshot(path)
    
    def close(self):
        """Close the browser."""
        self.adapter.close()
        self._connected = False
        self.logger.info("WebUIProxy closed.")


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Chat with web UIs via browser automation")
    parser.add_argument("url", help="Web UI URL (e.g., https://gemini.google.com)")
    parser.add_argument("-m", "--message", help="Message to send (interactive if not provided)")
    parser.add_argument("--user-data-dir", help="Browser profile directory (for persistent login)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--no-wait-login", action="store_true", help="Don't wait for login")
    
    args = parser.parse_args()
    
    proxy = WebUIProxy()
    print(proxy.connect(args.url, headless=args.headless, user_data_dir=args.user_data_dir))
    
    if not args.no_wait_login:
        print(proxy.wait_for_login())
    
    if args.message:
        response = proxy.say(args.message)
        print(f"\n🤖 Response: {response}")
    else:
        print("\n💬 Interactive mode. Type 'quit' to exit.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ("quit", "exit", "q"):
                    break
                elif user_input.lower() == "screenshot":
                    proxy.screenshot()
                    print("Screenshot saved")
                    continue
                elif not user_input:
                    continue
                
                response = proxy.say(user_input)
                print(f"🤖 Agent: {response}\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}\n")
    
    proxy.close()
    print("Session closed")
