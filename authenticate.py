#!/usr/bin/env python3
"""
TIDAL Authentication Helper

Run this script to authenticate with TIDAL. The session will be saved
and automatically used by the MCP server.

Usage:
    uv run python authenticate.py
"""

import json
import sys
from pathlib import Path

import tidalapi


def main():
    # Session file location (same as MCP server uses)
    session_dir = Path(__file__).parent / ".tidal-sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "session.json"

    session = tidalapi.Session()

    # Check if already authenticated
    if session_file.exists():
        try:
            with open(session_file, "r") as f:
                data = json.load(f)

            result = session.load_oauth_session(
                data["token_type"]["data"],
                data["access_token"]["data"],
                data["refresh_token"]["data"],
                None,
            )

            if result and session.check_login():
                print("Already authenticated with TIDAL!")
                print(f"Session file: {session_file}")
                return 0
        except Exception as e:
            print(f"Existing session invalid: {e}")
            session_file.unlink()

    # Start OAuth flow
    print("Starting TIDAL OAuth authentication...")
    print()

    login, future = session.login_oauth()

    auth_url = login.verification_uri_complete
    if not auth_url.startswith("http"):
        auth_url = "https://" + auth_url

    print("=" * 60)
    print("Please open this URL in your browser to authenticate:")
    print()
    print(f"  {auth_url}")
    print()
    print(f"Link expires in {int(login.expires_in)} seconds ({int(login.expires_in) // 60} minutes)")
    print("=" * 60)
    print()
    print("Waiting for you to complete authentication in browser...")

    # Wait for authentication
    try:
        future.result()
    except Exception as e:
        print(f"\nAuthentication failed: {e}")
        return 1

    # Verify and save
    if session.check_login():
        session_data = {
            "token_type": {"data": session.token_type or "Bearer"},
            "session_id": {"data": session.session_id or ""},
            "access_token": {"data": session.access_token},
            "refresh_token": {"data": session.refresh_token},
            "is_pkce": {"data": session.is_pkce},
        }
        with open(session_file, "w") as f:
            json.dump(session_data, f)

        print()
        print("Successfully authenticated with TIDAL!")
        print(f"Session saved to: {session_file}")
        print()
        print("You can now use the MCP server - all tools will work automatically.")
        return 0
    else:
        print("\nAuthentication failed - please try again")
        return 1


if __name__ == "__main__":
    sys.exit(main())
