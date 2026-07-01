# Google OAuth Integration for Setloader

This document explains how to set up and use Google OAuth authentication with the setloader application.

## 🎯 Overview

The setloader application now supports Google OAuth 2.0 authentication, allowing users to sign in with their Google accounts instead of using session-based authentication.

## 🔧 Setup Instructions

### 1. Google Cloud Console Setup

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Create a new project or select an existing one

2. **Enable Required APIs**
   - Go to "APIs & Services" > "Library"
   - Search for and enable "Google+ API" or "Google People API"

3. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Set application type to "Web application"
   - Add authorized redirect URIs:
     - `http://localhost:8002/auth/google/callback` (development)
     - `https://yourdomain.com/auth/google/callback` (production)

4. **Copy Credentials**
   - Copy the Client ID and Client Secret
   - Keep these secure and don't commit them to version control

### 2. Environment Configuration

#### Option A: Environment Variables
```bash
export GOOGLE_CLIENT_ID="your_client_id_here"
export GOOGLE_CLIENT_SECRET="your_client_secret_here"
export GOOGLE_REDIRECT_URI="http://localhost:8002/auth/google/callback"
```

#### Option B: .env File
Create a `.env` file in the project root:
```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8002/auth/google/callback
```

### 3. Automated Setup

Run the setup script to configure OAuth:
```bash
python setup_google_oauth.py
```

This script will:
- Check your current configuration
- Guide you through the setup process
- Create a `.env` file template if needed
- Open Google Cloud Console in your browser

## 🚀 Usage

### Backend Endpoints

The following OAuth endpoints are available:

- `GET /auth/google` - Initiate Google OAuth login
- `GET /auth/google/callback` - Handle OAuth callback
- `GET /auth/logout` - Logout user and revoke credentials
- `GET /auth/user` - Get authenticated user information

### Frontend Integration

The frontend includes a `GoogleAuth` component that handles:
- User authentication status
- Google login/logout
- User profile display
- Error handling

### User Data Structure

When a user signs in with Google, the following data is stored:

```json
{
  "user_id": "google_123456789",
  "google_id": "123456789",
  "email": "user@example.com",
  "name": "John Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "created_at": "2025-10-12T22:00:00.000Z",
  "last_login": "2025-10-12T22:00:00.000Z"
}
```

## 🔒 Security Features

- **Secure Token Storage**: OAuth tokens are stored securely in encrypted files
- **Automatic Token Refresh**: Tokens are automatically refreshed when needed
- **Credential Revocation**: Logout properly revokes Google credentials
- **Session Management**: User sessions are tied to Google authentication

## 🧪 Testing

### Test OAuth Configuration
```bash
python -c "from google_oauth import google_oauth; print('OAuth configured:', bool(google_oauth.client_id))"
```

### Test OAuth Endpoints
```bash
# Test login endpoint
curl http://localhost:8002/auth/google

# Test user info (requires authentication)
curl -H "X-Secret: change-me" -H "X-Session-ID: google_123456789" http://localhost:8002/auth/user
```

## 🐛 Troubleshooting

### Common Issues

1. **"No module named 'google'"**
   - Install required packages: `pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client`

2. **"Client ID not configured"**
   - Set environment variables or create `.env` file
   - Run `python setup_google_oauth.py` for guided setup

3. **"Redirect URI mismatch"**
   - Ensure redirect URI in Google Console matches your configuration
   - Check that the URI is exactly: `http://localhost:8002/auth/google/callback`

4. **"Invalid client"**
   - Verify Client ID and Client Secret are correct
   - Check that the OAuth consent screen is configured

### Debug Mode

Enable debug logging by setting:
```bash
export OAUTH_DEBUG=1
```

## 📁 File Structure

```
setloader/
├── google_oauth.py              # OAuth authentication module
├── oauth_config.py             # OAuth configuration
├── setup_google_oauth.py       # Setup script
├── GOOGLE_OAUTH_SETUP.md       # This documentation
├── oauth_credentials/          # Stored OAuth tokens (auto-created)
│   └── google_123456789_credentials.json
└── setlist-helper/
    └── components/
        └── google-auth.tsx     # Frontend OAuth component
```

## 🔄 Migration from Session-based Auth

The OAuth integration is designed to work alongside the existing session-based authentication:

- **New users**: Can sign in with Google OAuth
- **Existing users**: Continue using session-based authentication
- **Hybrid approach**: Both authentication methods are supported

## 🚀 Production Deployment

For production deployment:

1. **Update Redirect URIs**
   - Add your production domain to Google Console
   - Update `GOOGLE_REDIRECT_URI` environment variable

2. **Secure Configuration**
   - Use environment variables or secure secret management
   - Never commit credentials to version control

3. **HTTPS Required**
   - Google OAuth requires HTTPS in production
   - Ensure your production server uses SSL/TLS

## 📚 Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)
- [OAuth 2.0 Security Best Practices](https://tools.ietf.org/html/draft-ietf-oauth-security-topics)

## 🤝 Support

If you encounter issues with Google OAuth integration:

1. Check the troubleshooting section above
2. Verify your Google Cloud Console configuration
3. Review the application logs for error messages
4. Ensure all required packages are installed

---

**Note**: This OAuth integration provides a more secure and user-friendly authentication experience while maintaining compatibility with the existing setloader functionality.
