# Browser Automation Tools for Red Team Attacks

## Available Tools

### 1. Playwright (Default, Recommended)
**Pros:**
- ✅ Fast and reliable
- ✅ Well-tested in production
- ✅ Excellent selector support
- ✅ Built-in auto-waiting
- ✅ Multi-browser support (Chromium, Firefox, WebKit)
- ✅ Screenshot and video recording
- ✅ Network interception

**Cons:**
- ❌ Requires Node.js installation
- ❌ Steeper learning curve

**Use When:**
- Need reliable, production-ready automation
- Complex multi-step workflows
- Need screenshot/video evidence
- Network monitoring required

### 2. Dev-Browser (Alternative)
**Pros:**
- ✅ Python-native (easier for some developers)
- ✅ Simpler API for basic tasks
- ✅ Good for quick prototyping
- ✅ Integrated with some ML frameworks
- ✅ Lower resource usage for simple tasks

**Cons:**
- ❌ Less mature than Playwright
- ❌ May have edge cases with complex UIs
- ❌ Limited browser support

**Use When:**
- Prefer Python-native tooling
- Simple automation tasks
- Quick prototyping
- Resource-constrained environments

### 3. Puppeteer (Node.js only)
**Pros:**
- ✅ Mature and battle-tested
- ✅ Large ecosystem
- ✅ Good documentation

**Cons:**
- ❌ Chromium-only
- ❌ Less features than Playwright
- ❌ Requires Node.js

**Use When:**
- Already familiar with Puppeteer
- Chromium-specific features needed

### 4. Selenium (Legacy, Not Recommended)
**Pros:**
- ✅ Very mature
- ✅ Wide language support

**Cons:**
- ❌ Slow and unreliable
- ❌ Flaky tests
- ❌ Complex setup
- ❌ No auto-waiting

**Use When:**
- Legacy system requirements
- No other option available

## Comparison Matrix

| Feature | Playwright | Dev-Browser | Puppeteer | Selenium |
|---------|-----------|-------------|-----------|----------|
| Speed | ⚡⚡⚡ | ⚡⚡ | ⚡⚡⚡ | ⚡ |
| Reliability | ✅✅✅ | ✅✅ | ✅✅✅ | ✅ |
| Ease of Use | Medium | High | Medium | Low |
| Multi-browser | ✅ | ❌ | ❌ | ✅ |
| Auto-waiting | ✅ | ✅ | ⚠️ | ❌ |
| Network Control | ✅ | ⚠️ | ✅ | ❌ |
| Screenshots | ✅✅✅ | ✅✅ | ✅✅ | ✅ |
| Python Support | Via Playwright-Python | Native | ❌ | ✅ |
| Node.js Support | Native | ❌ | Native | Via WebDriver |

## Tool Selection Strategy

```python
def select_browser_tool(target_url, requirements):
    """
    Auto-select best browser automation tool
    """
    # Check if dev-browser is available
    try:
        import browser_use
        dev_browser_available = True
    except ImportError:
        dev_browser_available = False
    
    # Check if playwright is available
    playwright_available = check_playwright_installation()
    
    # Decision logic
    if requirements.get('network_monitoring'):
        # Playwright required for network interception
        return 'playwright'
    
    if requirements.get('multi_browser'):
        # Playwright supports multiple browsers
        return 'playwright'
    
    if requirements.get('simple_task') and dev_browser_available:
        # Dev-browser for simple tasks
        return 'dev-browser'
    
    if playwright_available:
        # Default to Playwright if available
        return 'playwright'
    
    if dev_browser_available:
        # Fallback to dev-browser
        return 'dev-browser'
    
    # No tool available
    raise Exception("No browser automation tool available")
```

## Implementation Patterns

### Playwright Pattern
```javascript
const { chromium } = require('playwright');

const browser = await chromium.launch({ headless: false });
const page = await browser.newPage();

await page.goto('http://target-url');
await page.locator('textarea').fill('payload');
await page.keyboard.press('Enter');

// Adaptive button detection
const buttons = ['Accept Plan', 'Approve', 'Confirm'];
for (const text of buttons) {
  const btn = page.locator(`button:has-text("${text}")`);
  if (await btn.isVisible()) {
    await btn.click();
    break;
  }
}

await browser.close();
```

### Dev-Browser Pattern
```python
from browser_use import Browser

browser = Browser()
page = browser.new_page('http://target-url')

# Fill input
page.fill('textarea', 'payload')
page.press('Enter')

# Adaptive button detection
buttons = ['Accept Plan', 'Approve', 'Confirm']
for text in buttons:
    if page.click_if_visible(f'button:has-text("{text}")'):
        break

browser.close()
```

## Hybrid Approach (Recommended)

Use Playwright as primary, dev-browser as fallback:

```python
class AdaptiveBrowserAutomation:
    def __init__(self, preferred_tool='playwright'):
        self.tool = self._select_available_tool(preferred_tool)
    
    def _select_available_tool(self, preferred):
        if preferred == 'playwright' and self._is_playwright_available():
            return PlaywrightAdapter()
        elif preferred == 'dev-browser' and self._is_dev_browser_available():
            return DevBrowserAdapter()
        else:
            # Try fallback
            if self._is_playwright_available():
                return PlaywrightAdapter()
            elif self._is_dev_browser_available():
                return DevBrowserAdapter()
            else:
                raise Exception("No browser tool available")
    
    def execute_attack(self, target_url, payload):
        return self.tool.execute(target_url, payload)
```

## Configuration

Add tool selection to config:

```yaml
# red-team config
browser_automation:
  preferred_tool: playwright  # or 'dev-browser', 'auto'
  fallback_enabled: true
  
  playwright:
    headless: false
    slow_mo: 50
    timeout: 30000
  
  dev_browser:
    headless: false
    timeout: 30000
```

## Recommendation for Red Team

**Primary: Playwright**
- More reliable for complex multi-step attacks
- Better debugging with screenshots
- Production-tested

**Fallback: Dev-Browser**
- Use if Playwright unavailable
- Good for simple attacks
- Faster for basic tasks

**Strategy:**
1. Try Playwright first
2. If Playwright fails or unavailable, use dev-browser
3. Report which tool was used in attack results
