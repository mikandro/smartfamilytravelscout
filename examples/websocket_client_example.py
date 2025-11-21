"""
WebSocket Client Example

This example demonstrates how to connect to the scraping WebSocket endpoint
and receive real-time updates during scraping operations.

Usage:
    python examples/websocket_client_example.py <job_id>

Example:
    python examples/websocket_client_example.py 123
"""

import asyncio
import json
import sys
from datetime import datetime

import websockets


async def listen_to_scraping_updates(job_id: int, websocket_url: str = "ws://localhost:8000"):
    """
    Connect to the WebSocket endpoint and listen for scraping updates.

    Args:
        job_id: ID of the scraping job to monitor
        websocket_url: Base WebSocket URL (default: ws://localhost:8000)
    """
    uri = f"{websocket_url}/ws/scraping/{job_id}"

    print(f"Connecting to WebSocket: {uri}")
    print("-" * 80)

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✓ Connected to job {job_id}")
            print(f"Listening for updates... (Press Ctrl+C to stop)\n")

            # Send initial ping
            await websocket.send("ping")

            while True:
                try:
                    # Receive message
                    message = await websocket.recv()

                    # Handle pong response
                    if message == "pong":
                        continue

                    # Parse JSON event
                    event = json.loads(message)

                    # Format timestamp
                    timestamp = datetime.fromisoformat(event["timestamp"]).strftime("%H:%M:%S")

                    # Print event with color coding
                    event_type = event["event_type"]
                    status = event["status"]
                    progress = event.get("progress")
                    results_count = event.get("results_count", 0)
                    msg = event.get("message", "")

                    # Color codes for different event types
                    color = {
                        "job_started": "\033[94m",  # Blue
                        "job_progress": "\033[93m",  # Yellow
                        "job_completed": "\033[92m",  # Green
                        "job_failed": "\033[91m",  # Red
                        "scraper_started": "\033[96m",  # Cyan
                        "scraper_completed": "\033[92m",  # Green
                        "scraper_failed": "\033[91m",  # Red
                        "results_updated": "\033[95m",  # Magenta
                    }.get(event_type, "\033[0m")  # Default

                    reset = "\033[0m"

                    # Build status line
                    status_parts = [
                        f"{color}[{timestamp}]",
                        f"[{event_type}]",
                        f"Status: {status}",
                    ]

                    if progress is not None:
                        status_parts.append(f"Progress: {progress:.1f}%")

                    status_parts.append(f"Results: {results_count}")

                    if msg:
                        status_parts.append(f"- {msg}")

                    status_parts.append(reset)

                    print(" ".join(status_parts))

                    # Print metadata if available
                    if event.get("metadata"):
                        metadata = event["metadata"]
                        if metadata:
                            print(f"  Metadata: {json.dumps(metadata, indent=2)}")

                    # Exit if job completed or failed
                    if event_type in ["job_completed", "job_failed"]:
                        print(f"\n{color}{'=' * 80}{reset}")
                        print(f"{color}Job finished with status: {status}{reset}")
                        print(f"{color}{'=' * 80}{reset}")
                        break

                except websockets.exceptions.ConnectionClosed:
                    print("\n✗ WebSocket connection closed")
                    break
                except json.JSONDecodeError as e:
                    print(f"✗ Failed to parse message: {e}")
                    continue
                except KeyboardInterrupt:
                    print("\n\n✗ Interrupted by user")
                    break

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ Failed to connect: {e}")
        print(f"  Make sure the server is running and job {job_id} exists")
    except Exception as e:
        print(f"✗ Error: {e}")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python examples/websocket_client_example.py <job_id>")
        print("Example: python examples/websocket_client_example.py 123")
        sys.exit(1)

    try:
        job_id = int(sys.argv[1])
    except ValueError:
        print("Error: job_id must be an integer")
        sys.exit(1)

    # Optional: custom WebSocket URL
    websocket_url = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8000"

    await listen_to_scraping_updates(job_id, websocket_url)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
