#!/usr/bin/env python3
"""
Google OAuth Setup Script

This script helps you set up Google OAuth authentication for the setloader application.
"""

import os
import webbrowser
from pathlib import Path

def print_header():
    print("🔐 GOOGLE OAUTH SETUP")
    print("=" * 50)
    print()

def print_steps():
    print("📋 SETUP STEPS:")
    print("1. Go to Google Cloud Console")
    print("2. Create a new project or select existing one")
    print("3. Enable Google+ API")
    print("4. Create OAuth 2.0 credentials")
    print("5. Configure redirect URIs")
    print("6. Set environment variables")
    print()

def open_google_console():
    """Open Google Cloud Console in browser."""
    url = "https://console.cloud.google.com/"
    print(f"🌐 Opening Google Cloud Console: {url}")
    try:
        webbrowser.open(url)
        print("✅ Browser opened successfully")
    except Exception as e:
        print(f"❌ Failed to open browser: {e}")
        print(f"Please manually open: {url}")

def check_environment():
    """Check if environment variables are set."""
    print("🔍 CHECKING ENVIRONMENT VARIABLES:")
    print("-" * 40)
    
    required_vars = [
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET',
        'GOOGLE_REDIRECT_URI'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask the secret for security
            if 'SECRET' in var:
                masked_value = value[:8] + '*' * (len(value) - 8)
            else:
                masked_value = value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    print()
    
    if missing_vars:
        print("⚠️  MISSING ENVIRONMENT VARIABLES:")
        for var in missing_vars:
            print(f"   - {var}")
        print()
        return False
    else:
        print("✅ All environment variables are set!")
        print()
        return True

def create_env_file():
    """Create a .env file template."""
    env_file = Path(".env")
    if env_file.exists():
        print(f"⚠️  .env file already exists at {env_file.absolute()}")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Skipping .env file creation")
            return
    
    env_content = """# Google OAuth Configuration
# Get these from Google Cloud Console: https://console.cloud.google.com/
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8002/auth/google/callback

# API Configuration
API_SECRET=change-me

# Server Configuration
HOST=localhost
PORT=8002
"""
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Created .env file at {env_file.absolute()}")
    print("📝 Please edit the .env file with your actual Google OAuth credentials")

def print_instructions():
    """Print detailed setup instructions."""
    print("📖 DETAILED INSTRUCTIONS:")
    print("-" * 40)
    print()
    print("1. GOOGLE CLOUD CONSOLE SETUP:")
    print("   • Go to https://console.cloud.google.com/")
    print("   • Create a new project or select existing one")
    print("   • Enable the Google+ API (or Google People API)")
    print()
    print("2. CREATE OAUTH 2.0 CREDENTIALS:")
    print("   • Go to 'Credentials' in the left sidebar")
    print("   • Click 'Create Credentials' > 'OAuth 2.0 Client IDs'")
    print("   • Set application type to 'Web application'")
    print("   • Add authorized redirect URIs:")
    print("     - http://localhost:8002/auth/google/callback (development)")
    print("     - https://yourdomain.com/auth/google/callback (production)")
    print()
    print("3. SET ENVIRONMENT VARIABLES:")
    print("   • Copy the Client ID and Client Secret")
    print("   • Set them as environment variables:")
    print("     export GOOGLE_CLIENT_ID='your_client_id_here'")
    print("     export GOOGLE_CLIENT_SECRET='your_client_secret_here'")
    print("     export GOOGLE_REDIRECT_URI='http://localhost:8002/auth/google/callback'")
    print()
    print("4. ALTERNATIVELY, USE .env FILE:")
    print("   • The script can create a .env file template")
    print("   • Edit the .env file with your credentials")
    print("   • The application will load variables from .env")
    print()

def test_configuration():
    """Test the OAuth configuration."""
    print("🧪 TESTING CONFIGURATION:")
    print("-" * 40)
    
    try:
        from oauth_config import validate_config
        if validate_config():
            print("✅ OAuth configuration is valid!")
            return True
        else:
            print("❌ OAuth configuration is invalid")
            return False
    except ImportError as e:
        print(f"❌ Failed to import oauth_config: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Main setup function."""
    print_header()
    print_steps()
    
    # Check current environment
    env_ok = check_environment()
    
    if not env_ok:
        print("🔧 SETUP OPTIONS:")
        print("1. Set environment variables manually")
        print("2. Create .env file template")
        print("3. Open Google Cloud Console")
        print()
        
        choice = input("Choose an option (1-3): ").strip()
        
        if choice == '1':
            print_instructions()
        elif choice == '2':
            create_env_file()
        elif choice == '3':
            open_google_console()
        else:
            print("Invalid choice. Exiting.")
            return
    
    print()
    
    # Test configuration
    if test_configuration():
        print("🎉 SETUP COMPLETE!")
        print("You can now run the application with Google OAuth authentication.")
    else:
        print("❌ SETUP INCOMPLETE")
        print("Please complete the setup steps above and try again.")

if __name__ == "__main__":
    main()
