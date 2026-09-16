#!/usr/bin/env python3
"""
Dropbox OAuth Helper - Get access/refresh tokens for the Show Recap app.

Usage:
    export DROPBOX_KEY="your-app-key"
    export DROPBOX_SECRET="your-app-secret"
    python dropbox_auth.py

This will:
1. Open a browser for Dropbox authorization
2. You'll copy the authorization code back
3. It will print the refresh token to save
"""

import os
import sys

try:
    import dropbox
    from dropbox import DropboxOAuth2FlowNoRedirect
except ImportError:
    print("Please install dropbox: pip install dropbox")
    sys.exit(1)


def main():
    app_key = os.environ.get("DROPBOX_KEY") or os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_SECRET") or os.environ.get("DROPBOX_APP_SECRET")
    
    if not app_key or not app_secret:
        print("Error: Set DROPBOX_KEY and DROPBOX_SECRET environment variables")
        print()
        print("Get these from: https://www.dropbox.com/developers/apps")
        print("  1. Create an app (or use existing)")
        print("  2. Copy App key and App secret")
        sys.exit(1)
    
    print("Dropbox OAuth Authorization")
    print("=" * 40)
    print()
    
    # Start OAuth flow
    auth_flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type='offline',  # Get refresh token for long-term access
    )
    
    authorize_url = auth_flow.start()
    
    print("1. Go to this URL in your browser:")
    print()
    print(f"   {authorize_url}")
    print()
    print("2. Click 'Allow' to authorize the app")
    print("3. Copy the authorization code")
    print()
    
    auth_code = input("Enter the authorization code: ").strip()
    
    if not auth_code:
        print("No code entered, aborting.")
        sys.exit(1)
    
    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print()
    print("=" * 40)
    print("SUCCESS! Save these values:")
    print("=" * 40)
    print()
    print(f"Access Token (short-lived):")
    print(f"  {oauth_result.access_token[:20]}...{oauth_result.access_token[-10:]}")
    print()
    print(f"Refresh Token (long-lived, save this!):")
    print(f"  {oauth_result.refresh_token}")
    print()
    print("Add to your environment or GitHub secrets:")
    print(f"  DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}")
    print()
    
    # Test the connection
    print("Testing connection...")
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=oauth_result.refresh_token,
        app_key=app_key,
        app_secret=app_secret,
    )
    
    account = dbx.users_get_current_account()
    print(f"Connected as: {account.name.display_name} ({account.email})")
    print()
    print("You're all set!")


if __name__ == "__main__":
    main()
