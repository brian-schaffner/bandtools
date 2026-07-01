#!/usr/bin/env python3
"""
Google OAuth Authentication Module

Handles Google OAuth 2.0 authentication for the setloader application.
"""

import hashlib
import json
import secrets
import time
from typing import Dict, Optional, Tuple
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth_config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, SCOPES

PENDING_OAUTH_TTL_SECONDS = 600


class GoogleOAuth:
    """Google OAuth 2.0 authentication handler."""
    
    def __init__(self):
        self.client_id = GOOGLE_CLIENT_ID
        self.client_secret = GOOGLE_CLIENT_SECRET
        self.redirect_uri = GOOGLE_REDIRECT_URI
        self.scopes = SCOPES
        
        # Create credentials directory
        self.credentials_dir = Path("oauth_credentials")
        self.credentials_dir.mkdir(exist_ok=True)
        self.pending_oauth_dir = self.credentials_dir / "pending"
        self.pending_oauth_dir.mkdir(exist_ok=True)

    def _pending_key(self, state: str) -> str:
        return hashlib.sha256(state.encode()).hexdigest()

    def _save_pending_oauth(self, state: str, code_verifier: str) -> None:
        path = self.pending_oauth_dir / f"{self._pending_key(state)}.json"
        with open(path, "w") as f:
            json.dump({"code_verifier": code_verifier, "created": time.time()}, f)

    def _load_pending_oauth(self, state: str) -> Optional[str]:
        path = self.pending_oauth_dir / f"{self._pending_key(state)}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("created", 0) > PENDING_OAUTH_TTL_SECONDS:
                return None
            return data.get("code_verifier")
        except (json.JSONDecodeError, OSError):
            return None
        finally:
            path.unlink(missing_ok=True)

    def _cleanup_stale_pending(self) -> None:
        now = time.time()
        for path in self.pending_oauth_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if now - data.get("created", 0) > PENDING_OAUTH_TTL_SECONDS:
                    path.unlink(missing_ok=True)
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)

    def get_authorization_url(self, state: str = None) -> str:
        """Generate Google OAuth authorization URL."""
        if not self.client_id:
            raise ValueError("Google Client ID not configured")
        if not self.client_secret:
            raise ValueError(
                "GOOGLE_CLIENT_SECRET is not configured. Add it to .env for your OAuth client."
            )

        self._cleanup_stale_pending()

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )

        if flow.code_verifier:
            self._save_pending_oauth(state, flow.code_verifier)

        return authorization_url, state
    
    def exchange_code_for_token(self, authorization_code: str, state: str = None) -> Tuple[Credentials, Dict]:
        """Exchange authorization code for access token."""
        if not self.client_id:
            raise ValueError("Google Client ID not configured")
        if not self.client_secret:
            raise ValueError(
                "GOOGLE_CLIENT_SECRET is not configured. Add it to .env for your OAuth client."
            )
        if not state:
            raise ValueError("Missing OAuth state. Please sign in again.")

        code_verifier = self._load_pending_oauth(state)
        if not code_verifier:
            raise ValueError(
                "OAuth session expired or PKCE verifier missing. Please sign in again."
            )

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        flow.code_verifier = code_verifier

        # Exchange the authorization code for credentials
        flow.fetch_token(code=authorization_code)
        credentials = flow.credentials
        
        # Get user info
        user_info = self.get_user_info(credentials)
        
        return credentials, user_info
    
    def get_user_info(self, credentials: Credentials) -> Dict:
        """Get user information from Google."""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return user_info
        except HttpError as e:
            raise Exception(f"Failed to get user info: {e}")
    
    def save_credentials(self, user_id: str, credentials: Credentials) -> None:
        """Save user credentials to file."""
        credentials_file = self.credentials_dir / f"{user_id}_credentials.json"
        
        # Convert credentials to dict
        creds_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        with open(credentials_file, 'w') as f:
            json.dump(creds_dict, f)
    
    def load_credentials(self, user_id: str) -> Optional[Credentials]:
        """Load user credentials from file."""
        credentials_file = self.credentials_dir / f"{user_id}_credentials.json"
        
        if not credentials_file.exists():
            return None
        
        try:
            with open(credentials_file, 'r') as f:
                creds_dict = json.load(f)
            
            credentials = Credentials.from_authorized_user_info(creds_dict, SCOPES)
            
            # Refresh token if needed
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self.save_credentials(user_id, credentials)
            
            return credentials
        except Exception as e:
            print(f"Error loading credentials for user {user_id}: {e}")
            return None
    
    def revoke_credentials(self, user_id: str) -> bool:
        """Revoke user credentials."""
        credentials = self.load_credentials(user_id)
        if credentials:
            try:
                credentials.revoke(Request())
                credentials_file = self.credentials_dir / f"{user_id}_credentials.json"
                if credentials_file.exists():
                    credentials_file.unlink()
                return True
            except Exception as e:
                print(f"Error revoking credentials for user {user_id}: {e}")
                return False
        return True
    
    def is_authenticated(self, user_id: str) -> bool:
        """Check if user is authenticated."""
        credentials = self.load_credentials(user_id)
        return credentials is not None and credentials.valid

# Global OAuth instance
google_oauth = GoogleOAuth()
