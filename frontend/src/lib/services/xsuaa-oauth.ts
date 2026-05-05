/**
 * XSUAA OAuth2 Service
 *
 * Handles OAuth2 Authorization Code Flow with PKCE for XSUAA authentication.
 * Loads configuration from default-env.json (local) or VCAP_SERVICES (Cloud Foundry)
 * via the /api/xsuaa-config API route, which uses @sap/xsenv server-side.
 */

interface XSUAACredentials {
  url: string;
  clientid: string;
  clientsecret?: string;
  uaadomain: string;
  xsappname: string;
  identityzone?: string;
  tenantid?: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Generate a random code verifier for PKCE
 */
function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return base64URLEncode(array);
}

/**
 * Generate code challenge from verifier
 */
async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return base64URLEncode(new Uint8Array(hash));
}

/**
 * Base64 URL encode (without padding)
 */
function base64URLEncode(buffer: Uint8Array): string {
  const base64 = btoa(String.fromCharCode(...buffer));
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
}

/**
 * Generate random state for CSRF protection
 */
function generateState(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return base64URLEncode(array);
}

class XSUAAOAuthService {
  private config: XSUAACredentials | null = null;
  private configPromise: Promise<XSUAACredentials> | null = null;

  /**
   * Initialize XSUAA configuration by fetching from API route
   * The API route reads from default-env.json or VCAP_SERVICES using @sap/xsenv
   */
  async initialize(): Promise<void> {
    if (this.config) {
      return;
    }

    if (this.configPromise) {
      await this.configPromise;
      return;
    }

    this.configPromise = this.fetchConfig();
    this.config = await this.configPromise;
    this.configPromise = null;
  }

  /**
   * Fetch XSUAA configuration from backend API
   */
  private async fetchConfig(): Promise<XSUAACredentials> {
    const response = await fetch('/api/xsuaa-config');

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Failed to load XSUAA configuration: ${error.error}`);
    }

    return await response.json();
  }

  /**
   * Get XSUAA configuration (synchronous)
   * Must call initialize() first
   */
  getConfig(): XSUAACredentials {
    if (!this.config) {
      throw new Error('XSUAA service not initialized. Call initialize() first.');
    }

    return this.config;
  }

  /**
   * Check if service is initialized
   */
  isInitialized(): boolean {
    return this.config !== null;
  }

  /**
   * Build authorization URL for XSUAA login with PKCE
   */
  async buildAuthorizationUrl(returnUrl?: string): Promise<string> {
    const config = this.getConfig();

    // Generate PKCE parameters
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    const state = generateState();

    // Store code verifier and return URL in session storage
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('xsuaa_code_verifier', codeVerifier);
      sessionStorage.setItem('xsuaa_state', state);
      if (returnUrl) {
        sessionStorage.setItem('xsuaa_return_url', returnUrl);
      }
    }

    // Build authorization URL
    const redirectUri = `${window.location.origin}/auth/callback`;
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: config.clientid,
      redirect_uri: redirectUri,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
      state: state,
    });

    return `${config.url}/oauth/authorize?${params.toString()}`;
  }

  /**
   * Exchange authorization code for access token
   */
  async exchangeCodeForToken(
    code: string,
    state: string
  ): Promise<TokenResponse> {
    const config = this.getConfig();

    // Verify state (CSRF protection)
    const storedState = sessionStorage.getItem('xsuaa_state');
    if (state !== storedState) {
      throw new Error('Invalid state parameter - possible CSRF attack');
    }

    // Get code verifier from storage
    const codeVerifier = sessionStorage.getItem('xsuaa_code_verifier');
    if (!codeVerifier) {
      throw new Error('Code verifier not found in session storage');
    }

    // Exchange code for token via backend proxy
    // (keeps client_secret secure on server side)
    const redirectUri = `${window.location.origin}/auth/callback`;

    const response = await fetch('/api/xsuaa-token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code: code,
        redirect_uri: redirectUri,
        code_verifier: codeVerifier,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Token exchange failed: ${error}`);
    }

    const tokenResponse: TokenResponse = await response.json();

    // Clean up session storage
    sessionStorage.removeItem('xsuaa_code_verifier');
    sessionStorage.removeItem('xsuaa_state');

    return tokenResponse;
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
    // Refresh token via backend proxy
    // (keeps client_secret secure on server side)
    const response = await fetch('/api/xsuaa-refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Token refresh failed: ${error}`);
    }

    return await response.json();
  }

  /**
   * Build XSUAA logout URL
   */
  buildLogoutUrl(postLogoutRedirectUri?: string): string {
    const config = this.getConfig();
    const redirectUri = postLogoutRedirectUri || window.location.origin;

    const params = new URLSearchParams({
      client_id: config.clientid,
      post_logout_redirect_uri: redirectUri,
    });

    return `${config.url}/oauth/logout?${params.toString()}`;
  }

  /**
   * Get return URL from session storage
   */
  getReturnUrl(): string {
    if (typeof window !== 'undefined') {
      const returnUrl = sessionStorage.getItem('xsuaa_return_url');
      sessionStorage.removeItem('xsuaa_return_url');
      return returnUrl || '/workspaces';
    }
    return '/workspaces';
  }
}

// Global singleton instance
export const xsuaaOAuthService = new XSUAAOAuthService();
