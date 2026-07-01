const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002';
const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET || 'change-me';

/** Resolve API base URL — use same-host /api when opened via Tailscale Serve or Fly. */
export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const { hostname, origin, protocol } = window.location;
    if (hostname.endsWith('.ts.net') && protocol.startsWith('http')) {
      return `${origin}/api`;
    }
    if (hostname.endsWith('.fly.dev') && protocol.startsWith('http')) {
      return `${origin}/api`;
    }
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8002';
    }
  }
  return DEFAULT_API_URL;
}

const API_BASE_URL = DEFAULT_API_URL;

function getSessionId(): string {
  if (typeof window === 'undefined') {
    return 'guest-session';
  }
  return localStorage.getItem('session_token') || localStorage.getItem('session_id') || 'guest-session';
}

export function getApiAuthHeaders(): Record<string, string> {
  return {
    'X-Secret': API_SECRET,
    'X-Session-ID': getSessionId(),
  };
}

export { API_BASE_URL, API_SECRET };

interface ApiResponse<T = any> {
  ok: boolean;
  error?: string;
  message?: string;
  data?: T;
}

interface UserStatus {
  user_id: string;
  user_email: string;
  backup_uploaded: boolean;
  backup_count: number;
  setlist_count: number;
  download_count: number;
  session_created: string;
  song_count: number;
  latest_backup?: {
    filename: string;
    uploaded_at: string;
    song_count: number;
  };
}

interface FileEntry {
  id: string;
  path: string;
  filename: string;
  uploaded_at: string;
  metadata: Record<string, any>;
}

interface UserFiles {
  backups: FileEntry[];
  setlists: FileEntry[];
  downloads: FileEntry[];
}

interface BackupVerificationResponse {
  ok: boolean;
  message?: string;
  file_id?: string;
  filename?: string;
  file_size?: number;
  uploaded_at?: string;
  song_count?: number;
  error?: string;
}

interface SetlistProcessingResponse {
  ok?: boolean;
  download_id?: string;
  filename?: string;
  download_url?: string;
  file_size?: number;
  created_at?: string;
  error?: string;
  code?: number;
  stdout?: string[];
  stderr?: string[];
  artifact?: string;
  processing_results?: {
    song_count: number;
    successful_mappings: number;
    unfound_titles: string[];
    all_titles: string[];
  };
}

class ApiService {
  private getHeaders(): HeadersInit {
    return {
      'X-Secret': API_SECRET,
      'Content-Type': 'application/json',
    };
  }

  private getSessionId(): string {
    const sessionId = localStorage.getItem('session_token') || localStorage.getItem('session_id');
    if (!sessionId) {
      console.warn('No session token found in localStorage. User may not be authenticated.');
      return 'guest-session';
    }
    return sessionId;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const sessionId = this.getSessionId();
    const baseUrl = getApiBaseUrl();

    let response: Response;
    try {
      response = await fetch(`${baseUrl}${endpoint}`, {
        ...options,
        headers: {
          ...this.getHeaders(),
          'X-Session-ID': sessionId,
          ...options.headers,
        },
      });
    } catch (error) {
      const hint =
        typeof window !== 'undefined' && window.location.hostname.endsWith('.ts.net')
          ? ' Check that SetLoader backend is running and Tailscale Serve is configured.'
          : ' Check that the backend is running on port 8002.';
      return {
        ok: false,
        error: error instanceof Error ? `${error.message}${hint}` : `Network error${hint}`,
      };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        ok: false,
        error: errorData.detail || `HTTP ${response.status}`,
        message: errorData.message,
      };
    }

    const data = await response.json();
    return {
      ok: true,
      data,
    };
  }

  async getUserStatus(): Promise<ApiResponse<UserStatus>> {
    return this.request<UserStatus>('/user/status');
  }

  async getUserFiles(): Promise<ApiResponse<UserFiles>> {
    return this.request<UserFiles>('/user/files');
  }

  async verifyBackup(file: File): Promise<ApiResponse<BackupVerificationResponse>> {
    const formData = new FormData();
    formData.append('backup', file);

    const response = await fetch(`${getApiBaseUrl()}/verify_backup`, {
      method: 'POST',
      headers: {
        'X-Secret': API_SECRET,
        'X-Session-ID': this.getSessionId(),
      },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        ok: false,
        error: data.detail || `HTTP ${response.status}`,
        message: data.message,
      };
    }

    return {
      ok: true,
      data,
    };
  }

  async processSetlist(file: File, setName: string = 'Set'): Promise<ApiResponse<SetlistProcessingResponse>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', setName);

    const response = await fetch(`${getApiBaseUrl()}/process_setlist_simple`, {
      method: 'POST',
      headers: {
        'X-Secret': API_SECRET,
        'X-Session-ID': this.getSessionId(),
      },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        ok: false,
        error: data.detail || `HTTP ${response.status}`,
        message: data.message,
        data: data,
      };
    }

    return {
      ok: true,
      data,
    };
  }

  downloadFile(fileId: string): string {
    const sessionId = this.getSessionId();
    return `${getApiBaseUrl()}/download_file/${fileId}?X-Secret=${encodeURIComponent(API_SECRET)}&X-Session-ID=${encodeURIComponent(sessionId)}`;
  }

  // Google OAuth methods - using getUserStatus instead of separate auth endpoint

  async login(): Promise<ApiResponse<any>> {
    const sessionId = this.getSessionId();
    const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
      method: 'POST',
      headers: {
        'X-Secret': API_SECRET,
        'X-Session-ID': sessionId,
      },
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      return {
        ok: false,
        error: data.detail || `HTTP ${response.status}`,
      };
    }

    return {
      ok: true,
      data,
    };
  }

  async logout(): Promise<void> {
    const sessionId = this.getSessionId();
    const response = await fetch(`${getApiBaseUrl()}/auth/logout`, {
      method: 'GET',
      headers: {
        'X-Secret': API_SECRET,
        'X-Session-ID': sessionId,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to logout: ${response.status}`);
    }
    
    // Clear session token from localStorage
    localStorage.removeItem('session_token');
    localStorage.removeItem('session_id');
  }

  getBaseUrl(): string {
    return getApiBaseUrl();
  }

  async getAdminErrors(): Promise<ApiResponse<any>> {
    return this.request('/admin/errors');
  }

  // Title mapping endpoints
  async getTitleMappings(): Promise<ApiResponse<{mappings: Record<string, string>, count: number}>> {
    return this.request('/user/title-mappings');
  }

  // Alias used by components
  async getUserTitleMappings(): Promise<ApiResponse<{mappings: Record<string, string>, count: number}>> {
    return this.getTitleMappings();
  }

  async saveTitleMappings(mappings: Record<string, string>): Promise<ApiResponse<{ok: boolean, message: string, count: number}>> {
    return this.request('/user/title-mappings', {
      method: 'POST',
      body: JSON.stringify(mappings),
    });
  }

  async saveTitleMapping(pdf_title: string, catalog_title: string, catalog_song_id?: string): Promise<ApiResponse<{ok: boolean, mapping: any}>> {
    return this.request('/user/title-mappings', {
      method: 'POST',
      body: JSON.stringify({ pdf_title, catalog_title, catalog_song_id }),
    })
  }

  async getUserCatalog(): Promise<ApiResponse<{catalog: string[], count: number}>> {
    return this.request('/user/catalog');
  }

  async reprocessSetlist(): Promise<ApiResponse<{ok: boolean, message: string, download_url: string, file_id: string}>> {
    return this.request('/user/reprocess-setlist', {
      method: 'POST',
    });
  }

  async verifyTitles(titles: string[]): Promise<ApiResponse<{
    results: Array<{
      title: string;
      status: 'exact_match' | 'mapped' | 'dropped' | 'needs_mapping';
      mapped_to: string | null;
      suggestions: Array<{title: string, score: number}>;
    }>;
    total: number;
    needs_mapping: number;
  }>> {
    return this.request('/user/verify-titles', {
      method: 'POST',
      body: JSON.stringify(titles),
    });
  }

  async getArchive(): Promise<ApiResponse<any>> {
    return this.request('/user/archive');
  }

  // Alias for backwards compatibility with components
  async getUserArchive(): Promise<ApiResponse<any>> {
    return this.getArchive();
  }

  async reprocessArchiveItem(itemType: string, itemId: string): Promise<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('item_type', itemType);
    formData.append('item_id', itemId);
    
    const response = await fetch(`${getApiBaseUrl()}/user/reprocess-archive`, {
      method: 'POST',
      headers: {
        'X-Secret': API_SECRET,
        'X-Session-ID': this.getSessionId(),
      },
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        ok: false,
        error: data.detail || `HTTP ${response.status}`,
        message: data.message,
      };
    }

    return {
      ok: true,
      data,
    };
  }

  async deleteArchiveItem(itemType: string, itemId: string): Promise<ApiResponse<any>> {
    return this.request(`/user/archive/${itemType}/${itemId}`, {
      method: 'DELETE',
    });
  }
}

export const apiService = new ApiService();
export type { UserStatus, FileEntry, UserFiles, BackupVerificationResponse, SetlistProcessingResponse };
