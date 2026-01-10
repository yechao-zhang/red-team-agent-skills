#!/usr/bin/env python3
"""
Test all browser modes:
0. Using dev-browser (New Default)
1. Using playwright-skill (Legacy)
2. Direct Playwright script (Fallback)

Usage:
    python test_browser_modes.py <target_url>
"""

import sys
sys.path.insert(0, "/Users/gaoyang/.claude/skills/red-team/scripts")

from transport import TransportConfig, TransportFactory


def test_dev_browser_mode(url: str):
    """Test Mode 0: Using dev-browser (New Default)"""
    print(f"\n{'='*60}")
    print(f"MODE 0: Using dev-browser (New Default)")
    print(f"{'='*60}")

    config = TransportConfig(
        target_url=url,
        transport_type="browser",
        headless=False,
        use_dev_browser=True,
        use_playwright_skill=False
    )

    transport = TransportFactory.create(config)
    payload = "Test payload for dev-browser mode"

    instruction = transport.send(payload)

    print(f"\nGenerated Instruction:")
    print(f"  Method: {instruction['method']}")
    print(f"  Description: {instruction['description']}")

    if instruction["method"] == "skill":
        print(f"  Skill: {instruction['skill']}")
        print(f"\nTask Description:")
        print(f"  {instruction['args'][:200]}...")
        print(f"\nSubagent should execute:")
        print(f"  Skill('{instruction['skill']}', args=<task_description>)")

    transport.close()
    return instruction


def test_playwright_skill_mode(url: str):
    """Test Mode 1: Using playwright-skill"""
    print(f"\n{'='*60}")
    print(f"MODE 1: Using playwright-skill (Legacy)")
    print(f"{'='*60}")

    config = TransportConfig(
        target_url=url,
        transport_type="browser",
        headless=False,
        use_dev_browser=False, # Explicitly disable dev-browser
        use_playwright_skill=True  # Use playwright-skill
    )

    transport = TransportFactory.create(config)
    payload = "Test payload for playwright-skill mode"

    instruction = transport.send(payload)

    print(f"\nGenerated Instruction:")
    print(f"  Method: {instruction['method']}")
    print(f"  Description: {instruction['description']}")

    if instruction["method"] == "skill":
        print(f"  Skill: {instruction['skill']}")
        print(f"\nTask Description:")
        print(f"  {instruction['args'][:200]}...")
        print(f"\nSubagent should execute:")
        print(f"  Skill('{instruction['skill']}', args=<task_description>)")

    transport.close()
    return instruction


def test_direct_script_mode(url: str):
    """Test Mode 2: Direct Playwright script"""
    print(f"\n{'='*60}")
    print(f"MODE 2: Direct Playwright Script (Fallback)")
    print(f"{'='*60}")

    config = TransportConfig(
        target_url=url,
        transport_type="browser",
        headless=False,
        use_dev_browser=False, # Explicitly disable dev-browser
        use_playwright_skill=False  # Generate script directly
    )

    transport = TransportFactory.create(config)
    payload = "Test payload for direct script mode"

    instruction = transport.send(payload)

    print(f"\nGenerated Instruction:")
    print(f"  Method: {instruction['method']}")
    print(f"  Description: {instruction['description']}")

    if instruction["method"] == "bash":
        print(f"  Command: {instruction['command']}")
        print(f"\nScript saved to: /tmp/red_team_browser_attack.py")
        print(f"\nSubagent should execute:")
        print(f"  Bash('{instruction['command']}')")

    transport.close()
    return instruction


def compare_modes():
    """Print comparison table"""
    print(f"\n{'='*60}")
    print(f"COMPARISON: dev-browser vs playwright-skill vs Direct Script")
    print(f"{'='*60}\n")

    comparison = """
| Feature                  | dev-browser (Default)| playwright-skill (Legacy)| Direct Script        |
|--------------------------|----------------------|--------------------------|----------------------|
| Reusability              | ✅ High (shared)     | ✅ High (shared)         | ❌ Low (red-team only)|
| Maintenance              | ✅ External          | ✅ External              | ❌ Internal          |
| Flexibility              | ✅ Very flexible     | ✅ Very flexible         | ⚠️  Fixed logic      |
| Dependencies             | dev-browser          | playwright-skill         | Just playwright      |
| Code Complexity          | Low (task desc)      | Low (task desc)          | High (Python code)   |
| Updates/Improvements     | ✅ Automatic         | ✅ Automatic             | ❌ Manual            |
| Recommended              | ✅ YES (default)     | ⚠️  Legacy               | ⚠️  Fallback only    |

Recommendation: Use dev-browser (Mode 0) by default.
"""
    print(comparison)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_browser_modes.py <target_url>")
        print("\nExample:")
        print("  python test_browser_modes.py http://localhost:8082")
        sys.exit(1)

    target_url = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"Testing Browser Transport Modes")
    print(f"{'='*60}")
    print(f"Target URL: {target_url}\n")

    try:
        # Test Mode 0: dev-browser
        instruction0 = test_dev_browser_mode(target_url)

        # Test Mode 1: playwright-skill
        instruction1 = test_playwright_skill_mode(target_url)

        # Test Mode 2: Direct script
        instruction2 = test_direct_script_mode(target_url)

        # Compare
        compare_modes()

        print(f"\n{'='*60}")
        print(f"Test Complete")
        print(f"{'='*60}")
        print(f"✅ Mode 0 (dev-browser): {instruction0['method']}")
        print(f"✅ Mode 1 (playwright-skill): {instruction1['method']}")
        print(f"✅ Mode 2 (Direct script): {instruction2['method']}")
        print(f"\n🎯 Recommendation: Use Mode 0 (dev-browser)")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
