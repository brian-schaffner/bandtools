# Setlist Helper UI Integration

This document describes the integration between the new Next.js UI (`setlist-helper/`) and the existing FastAPI backend (`server.py`).

## Overview

The integration provides a modern web interface for the setloader system with the following key features:

- **User Session Management**: Each user gets a unique session ID for file tracking
- **Backup Verification**: Users must upload a backup file before processing setlists
- **File Association**: All uploaded files are associated with the user's session
- **Download Management**: Generated files are available for download through the UI
- **Error Handling**: Graceful error handling with user-friendly messages

## Architecture

### Backend Changes (server.py)

#### New Endpoints

1. **`POST /verify_backup`** - Verify and store backup files
   - Replaces the old `/update_catalog` behavior
   - Stores backup files in user-specific directories
   - Returns verification status instead of processing

2. **`POST /process_setlist`** - Process setlist files
   - Replaces the old `/run` endpoint behavior
   - Requires backup to be uploaded first
   - Returns download URL instead of emailing

3. **`GET /user/status`** - Get user session status
   - Returns backup upload status and file counts
   - Used by UI to determine available actions

4. **`GET /user/files`** - Get user's file history
   - Returns lists of backups, setlists, and downloads
   - Enables file management and history

5. **`GET /download_file/{file_id}`** - Download user files
   - Secure file downloads by file ID
   - User can only download their own files

6. **`GET /admin/errors`** - Admin error information
   - Detailed system information for debugging
   - Error logs and system health

#### User Management

- **Session-based**: Users identified by `X-Session-ID` header
- **File Storage**: User files stored in `user_data/{user_id}/`
- **File Tracking**: All files tracked with metadata (upload time, size, etc.)

### Frontend Changes (setlist-helper/)

#### API Service (`lib/api.ts`)

- Centralized API communication
- Session management with localStorage
- Type-safe API responses
- Error handling and retry logic

#### Updated Components

1. **Main Page (`app/page.tsx`)**
   - Real API integration for backup and setlist uploads
   - Error handling and user feedback
   - Backup requirement enforcement

2. **Initial Setup (`components/initial-setup.tsx`)**
   - Real backup verification
   - Status persistence across sessions

3. **File Upload Zone (`components/file-upload-zone.tsx`)**
   - Enhanced with loading states
   - Better error feedback

## Configuration

### Environment Variables

Create `.env.local` in the `setlist-helper/` directory:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_SECRET=change-me
```

### Backend Configuration

The backend uses the same `SECRET` environment variable for authentication:

```bash
export SECRET=change-me
```

## Usage

### Starting the System

1. **Start the Backend**:
   ```bash
   cd /usr/local/src/setloader
   python server.py
   ```

2. **Start the UI** (in a separate terminal):
   ```bash
   cd /usr/local/src/setloader
   ./start-ui.sh
   ```

3. **Access the UI**: http://localhost:3000

### User Flow

1. **Initial Setup**: User uploads a Song Book Pro backup file
2. **Backup Verification**: System verifies and stores the backup
3. **Setlist Upload**: User uploads PDF/image setlist files
4. **Processing**: System processes setlist using the backup database
5. **Download**: User downloads the generated Song Book Pro backup

### File Management

- **Backup Files**: Stored in `user_data/{user_id}/backup_*`
- **Setlist Files**: Stored in `user_data/{user_id}/setlist_*`
- **Download Files**: Stored in `user_data/{user_id}/download_*`

## Security

- **Authentication**: X-Secret header for API access
- **Session Isolation**: Users can only access their own files
- **File Validation**: Proper file type checking
- **CORS**: Configured for localhost development

## Testing

Run the integration test:

```bash
cd /usr/local/src/setloader
python test-integration.py
```

This tests all API endpoints and the complete user flow.

## Error Handling

### Backend Errors
- **400**: Bad request (missing backup, invalid file type)
- **401**: Unauthorized (invalid secret)
- **403**: Forbidden (invalid session)
- **404**: File not found
- **500**: Server error (processing failure)

### Frontend Errors
- **Network Errors**: Connection issues, timeouts
- **Validation Errors**: File type, size validation
- **User Feedback**: Clear error messages with recovery suggestions

## Development

### Adding New Features

1. **Backend**: Add new endpoints in `server.py`
2. **Frontend**: Add API calls in `lib/api.ts`
3. **Components**: Update UI components to use new APIs
4. **Testing**: Add tests to `test-integration.py`

### File Structure

```
setloader/
├── server.py                 # FastAPI backend
├── setlist-helper/           # Next.js frontend
│   ├── app/
│   │   └── page.tsx         # Main UI page
│   ├── components/
│   │   ├── file-upload-zone.tsx
│   │   ├── initial-setup.tsx
│   │   └── ...
│   └── lib/
│       └── api.ts           # API service
├── user_data/               # User file storage
└── test-integration.py     # Integration tests
```

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure backend CORS is configured for localhost:3000
2. **Authentication**: Check that SECRET matches between frontend and backend
3. **File Uploads**: Verify file types and sizes are within limits
4. **Session Issues**: Clear localStorage to reset session

### Debug Mode

Set `DEBUG_NO_CLEANUP=true` to prevent file cleanup for debugging.

### Logs

Check server logs for detailed error information:
- `logs/setloader.log` - General logs
- `logs/setloader-error.log` - Error logs
