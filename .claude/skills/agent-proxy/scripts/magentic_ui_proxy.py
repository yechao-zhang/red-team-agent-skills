#!/usr/bin/env python3
"""
Custom adapter for Magentic-UI using WebSocket API
"""
import asyncio
import json
import sys
import aiohttp
import websockets

BASE_URL = "http://localhost:8082"
WS_URL = "ws://localhost:8082"
USER_ID = "agent-proxy-user"


async def send_to_magentic_ui(message: str):
    """Send a message to Magentic-UI via its WebSocket API"""

    print(f"🔌 Connecting to Magentic-UI at {BASE_URL}...")

    # Step 1: Create a session
    async with aiohttp.ClientSession() as session:
        session_data = {
            "id": 0,
            "user_id": USER_ID,
            "name": "Agent Proxy Session",
            "tags": ["agent-proxy"],
            "team_config": {},
        }

        async with session.post(f"{BASE_URL}/api/sessions/", json=session_data) as resp:
            if resp.status != 200:
                print(f"❌ Failed to create session: {resp.status}")
                print(await resp.text())
                return None

            result = await resp.json()
            session_id = result["data"]["id"]
            print(f"✅ Created session {session_id}")

        # Step 2: Get the auto-created run
        async with session.get(f"{BASE_URL}/api/sessions/{session_id}/runs?user_id={USER_ID}") as resp:
            if resp.status != 200:
                print(f"❌ Failed to get runs: {resp.status}")
                return None

            result = await resp.json()
            if not result["data"]["runs"]:
                print("❌ No run found")
                return None

            run_id = result["data"]["runs"][0]["id"]
            print(f"✅ Got run {run_id}")

    # Step 3: Connect via WebSocket and send message
    ws_url = f"{WS_URL}/api/ws/runs/{run_id}"

    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"✅ Connected to WebSocket")

            # Send start message with the user's query
            start_message = {
                "type": "start",
                "task": message,
                "files": [],
                "team_config": {
                    "agents": [],
                    "model": "gpt-4"
                },
                "settings_config": {}
            }

            await websocket.send(json.dumps(start_message))
            print(f"📤 Sent message to Magentic-UI")
            print(f"🔗 View at: {BASE_URL}/?sessionId={session_id}")

            # Listen for responses
            print("\n--- Agent Response ---")
            full_response = []

            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    msg_type = data.get('type', 'unknown')

                    if msg_type == 'stream':
                        content = data.get('content', '')
                        if content:
                            print(content, end='', flush=True)
                            full_response.append(content)

                    elif msg_type == 'message':
                        content = data.get('content', '')
                        if content:
                            print(content)
                            full_response.append(content)

                    elif msg_type == 'error':
                        print(f"\n❌ Error: {data.get('error')}")
                        break

                    elif msg_type in ['complete', 'stopped']:
                        print(f"\n✅ Run {msg_type}")
                        break

            except asyncio.TimeoutError:
                print("\n⏱️ Response timeout")

            return ''.join(full_response)

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python magentic_ui_proxy.py <message>")
        sys.exit(1)

    message = ' '.join(sys.argv[1:])
    response = asyncio.run(send_to_magentic_ui(message))

    if response:
        print("\n" + "="*50)
        print("✅ Message sent successfully")
    else:
        print("\n" + "="*50)
        print("❌ Failed to send message")
        sys.exit(1)


if __name__ == "__main__":
    main()
