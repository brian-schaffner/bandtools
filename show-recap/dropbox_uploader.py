#!/usr/bin/env python3
"""
Dropbox Uploader - Upload processed show MP3s to Dropbox and get share links.

Requires:
    - DROPBOX_ACCESS_TOKEN or DROPBOX_REFRESH_TOKEN env var
    - pip install dropbox
"""

import os
from pathlib import Path
from typing import List, Dict, Optional

try:
    import dropbox
    from dropbox.files import WriteMode
    from dropbox.sharing import RequestedVisibility
    DROPBOX_AVAILABLE = True
except ImportError:
    DROPBOX_AVAILABLE = False


class DropboxUploader:
    """Upload files to Dropbox and create share links."""
    
    def __init__(
        self,
        access_token: str = None,
        refresh_token: str = None,
        app_key: str = None,
        app_secret: str = None,
        folder: str = "/Show Recap",
    ):
        """
        Initialize the uploader.
        
        Args:
            access_token: Dropbox access token (or DROPBOX_ACCESS_TOKEN env)
            refresh_token: Dropbox refresh token (or DROPBOX_REFRESH_TOKEN env)
            app_key: Dropbox app key (or DROPBOX_APP_KEY env)
            app_secret: Dropbox app secret (or DROPBOX_APP_SECRET env)
            folder: Dropbox folder to upload to
        """
        self.access_token = access_token or os.environ.get("DROPBOX_ACCESS_TOKEN")
        self.refresh_token = refresh_token or os.environ.get("DROPBOX_REFRESH_TOKEN")
        # Support both naming conventions for app credentials
        self.app_key = app_key or os.environ.get("DROPBOX_KEY") or os.environ.get("DROPBOX_APP_KEY")
        self.app_secret = app_secret or os.environ.get("DROPBOX_SECRET") or os.environ.get("DROPBOX_APP_SECRET")
        self.folder = folder
        self.dbx = None
        
        if not DROPBOX_AVAILABLE:
            print("[DROPBOX] Warning: dropbox package not installed")
            return
        
        if self.access_token:
            self.dbx = dropbox.Dropbox(self.access_token)
            print(f"[DROPBOX] Initialized with access token")
        elif self.refresh_token and self.app_key and self.app_secret:
            self.dbx = dropbox.Dropbox(
                oauth2_refresh_token=self.refresh_token,
                app_key=self.app_key,
                app_secret=self.app_secret,
            )
            print(f"[DROPBOX] Initialized with refresh token")
        else:
            print("[DROPBOX] Warning: No credentials configured")
            print("  Set DROPBOX_ACCESS_TOKEN or DROPBOX_REFRESH_TOKEN + APP_KEY + APP_SECRET")
    
    @property
    def available(self) -> bool:
        """Check if Dropbox is available."""
        return self.dbx is not None
    
    def upload_file(
        self,
        local_path: Path,
        remote_name: str = None,
        subfolder: str = None,
    ) -> Optional[str]:
        """
        Upload a file to Dropbox.
        
        Args:
            local_path: Path to local file
            remote_name: Name to use on Dropbox (default: same as local)
            subfolder: Subfolder within the base folder
            
        Returns:
            Dropbox path of uploaded file, or None on failure
        """
        if not self.available:
            return None
        
        local_path = Path(local_path)
        if not local_path.exists():
            print(f"[DROPBOX] Error: File not found: {local_path}")
            return None
        
        remote_name = remote_name or local_path.name
        
        if subfolder:
            remote_path = f"{self.folder}/{subfolder}/{remote_name}"
        else:
            remote_path = f"{self.folder}/{remote_name}"
        
        file_size = local_path.stat().st_size
        print(f"[DROPBOX] Uploading {local_path.name} ({file_size / 1024 / 1024:.1f} MB)...")
        
        try:
            with open(local_path, "rb") as f:
                # For large files, use upload session
                if file_size > 150 * 1024 * 1024:  # 150 MB
                    self._upload_large_file(f, remote_path, file_size)
                else:
                    self.dbx.files_upload(
                        f.read(),
                        remote_path,
                        mode=WriteMode.overwrite,
                    )
            
            print(f"[DROPBOX] Uploaded: {remote_path}")
            return remote_path
        
        except Exception as e:
            print(f"[DROPBOX] Upload failed: {e}")
            return None
    
    def _upload_large_file(self, f, remote_path: str, file_size: int):
        """Upload a large file using upload sessions."""
        CHUNK_SIZE = 50 * 1024 * 1024  # 50 MB chunks
        
        session_start = self.dbx.files_upload_session_start(f.read(CHUNK_SIZE))
        cursor = dropbox.files.UploadSessionCursor(
            session_id=session_start.session_id,
            offset=f.tell(),
        )
        
        while f.tell() < file_size:
            remaining = file_size - f.tell()
            
            if remaining <= CHUNK_SIZE:
                # Final chunk
                self.dbx.files_upload_session_finish(
                    f.read(CHUNK_SIZE),
                    cursor,
                    dropbox.files.CommitInfo(
                        path=remote_path,
                        mode=WriteMode.overwrite,
                    ),
                )
            else:
                self.dbx.files_upload_session_append_v2(
                    f.read(CHUNK_SIZE),
                    cursor,
                )
                cursor.offset = f.tell()
            
            progress = f.tell() / file_size * 100
            print(f"[DROPBOX]   {progress:.0f}%...")
    
    def get_share_link(self, remote_path: str) -> Optional[str]:
        """
        Get or create a share link for a file.
        
        Args:
            remote_path: Dropbox path to the file
            
        Returns:
            Share link URL, or None on failure
        """
        if not self.available:
            return None
        
        try:
            # Try to get existing link
            links = self.dbx.sharing_list_shared_links(path=remote_path)
            if links.links:
                return links.links[0].url
            
            # Create new link
            link = self.dbx.sharing_create_shared_link_with_settings(
                remote_path,
                dropbox.sharing.SharedLinkSettings(
                    requested_visibility=RequestedVisibility.public,
                ),
            )
            return link.url
        
        except dropbox.exceptions.ApiError as e:
            if "shared_link_already_exists" in str(e):
                # Link exists, fetch it
                links = self.dbx.sharing_list_shared_links(path=remote_path)
                if links.links:
                    return links.links[0].url
            print(f"[DROPBOX] Failed to get share link: {e}")
            return None
    
    def upload_show(
        self,
        mp3_files: List[Path],
        show_name: str,
        show_date: str,
    ) -> Dict[str, str]:
        """
        Upload show MP3s and return share links.
        
        Args:
            mp3_files: List of MP3 file paths
            show_name: Name of the show
            show_date: Date of the show (YYYY-MM-DD)
            
        Returns:
            Dict mapping filename to share link
        """
        if not self.available:
            return {}
        
        subfolder = f"{show_date} - {show_name}"
        links = {}
        
        for mp3 in mp3_files:
            remote_path = self.upload_file(mp3, subfolder=subfolder)
            if remote_path:
                link = self.get_share_link(remote_path)
                if link:
                    links[mp3.name] = link
        
        return links
    
    def create_folder_link(self, show_name: str, show_date: str) -> Optional[str]:
        """Create a share link for the show folder."""
        if not self.available:
            return None
        
        folder_path = f"{self.folder}/{show_date} - {show_name}"
        
        try:
            # Ensure folder exists
            try:
                self.dbx.files_create_folder_v2(folder_path)
            except:
                pass  # Folder may already exist
            
            return self.get_share_link(folder_path)
        except Exception as e:
            print(f"[DROPBOX] Failed to create folder link: {e}")
            return None


if __name__ == "__main__":
    import sys
    
    uploader = DropboxUploader()
    
    if not uploader.available:
        print("Dropbox not configured.")
        print("Set DROPBOX_ACCESS_TOKEN environment variable.")
        sys.exit(1)
    
    # Test with account info
    try:
        account = uploader.dbx.users_get_current_account()
        print(f"Connected as: {account.name.display_name}")
        print(f"Email: {account.email}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)
