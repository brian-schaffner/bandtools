#!/usr/bin/env python3
"""
Google OAuth Configuration

This file contains the configuration for Google OAuth authentication.
You need to set up a Google Cloud Console project and configure OAuth 2.0 credentials.

Steps to set up Google OAuth:
1. Go to https://console.cloud.google.com/
2. Create a new project or select an existing one
3. Enable the Google+ API
4. Go to "Credentials" in the left sidebar
5. Click "Create Credentials" > "OAuth 2.0 Client IDs"
6. Set application type to "Web application"
7. Add authorized redirect URIs:
   - http://localhost:8002/auth/google/callback (for development)
   - https://yourdomain.com/auth/google/callback (for production)
8. Copy the Client ID and Client Secret to the environment variables below
"""

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_env_file() -> None:
    """Load environment variables from .env."""
    if load_dotenv:
        load_dotenv()
        return
    env_file = Path('.env')
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _load_oauth_from_saved_credentials() -> None:
    """Restore client id/secret from a prior successful OAuth login if .env lacks them."""
    env_client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    env_client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    if env_client_id and env_client_secret:
        return
    # .env client id wins — saved credentials may belong to a different OAuth client.
    if env_client_id:
        return
    creds_dir = Path('oauth_credentials')
    if not creds_dir.is_dir():
        return
    for path in sorted(creds_dir.glob('*_credentials.json'), reverse=True):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        client_id = data.get('client_id') or ''
        client_secret = data.get('client_secret') or ''
        if client_id and client_secret:
            os.environ.setdefault('GOOGLE_CLIENT_ID', client_id)
            os.environ.setdefault('GOOGLE_CLIENT_SECRET', client_secret)
            return


load_env_file()
_load_oauth_from_saved_credentials()


def _default_redirect_uri() -> str:
    """Pick redirect URI from env or infer from public app URL."""
    explicit = os.getenv('GOOGLE_REDIRECT_URI', '').strip()
    if explicit:
        return explicit
    app_url = os.getenv('APP_URL', '').strip().rstrip('/')
    if app_url:
        return f'{app_url}/auth/google/callback'
    fly_app = os.getenv('FLY_APP_NAME', '').strip()
    if fly_app:
        return f'https://{fly_app}.fly.dev/auth/google/callback'
    tailnet_host = os.getenv('TAILNET_HOST', '').strip().rstrip('.')
    if tailnet_host:
        return f'https://{tailnet_host}/auth/google/callback'
    return 'http://localhost:3002/auth/google/callback'


# Google OAuth 2.0 Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = _default_redirect_uri()

# OAuth 2.0 Scopes
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

# Configuration validation
def validate_config():
    """Validate that all required OAuth configuration is present."""
    missing = []
    
    if not GOOGLE_CLIENT_ID:
        missing.append('GOOGLE_CLIENT_ID')
    if not GOOGLE_CLIENT_SECRET:
        missing.append('GOOGLE_CLIENT_SECRET')
    
    if missing:
        print("❌ Missing required Google OAuth configuration:")
        for item in missing:
            print(f"   - {item}")
        print("\n📝 To fix this:")
        print("1. Set up a Google Cloud Console project")
        print("2. Create OAuth 2.0 credentials")
        print("3. Set the environment variables:")
        for item in missing:
            print(f"   export {item}=your_value_here")
        print("\n🔗 See oauth_config.py for detailed setup instructions")
        return False
    
    print("✅ Google OAuth configuration is valid")
    return True

if __name__ == "__main__":
    validate_config()
