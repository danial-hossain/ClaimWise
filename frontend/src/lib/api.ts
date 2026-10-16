import {
  HealthResponse,
  ReadinessResponse,
  PolicyExtractionResult,
  CostCalculationInput,
  CostCalculationResult,
  QARequest,
  QAResponse,
  QAPipelineStatus,
  BillExtractionResult,
  BillLineItem,
  ClaimRecord,
  ClaimIntakePayload,
  ClaimChecklistItem,
  ExplanationOfBenefits,
  SandboxPayerOutcome,
  ComparisonCreateRequest,
  ComparisonRecord,
  ComparisonCostSimulation,
  CostSimulationAssumption,
  ClaimAppealDraft,
  AppealDraftCreateRequest,
  AppealDraftUpdateRequest,
  AppealExportPackage,
  AuditEvent,
  AuditVerificationResult,
  BenchmarkExecutionReport,
  CoverageScenarioRequest,
  CoverageGapAnalysisResult,
  CoverageGapReportResponse,
  PresetScenarioItem,
  IncidentQuestionnaireSchema,
  IncidentQuestionnaireRequest,
  IncidentGuidanceResult,
  PortfolioAnalysisRequest,
  PortfolioAnalysisResult,
  AuthUser,
  AuthResponse,
  LoginPayload,
  SignUpPayload,
  DemoLoginPayload,
} from '@/types/api';


export function getBackendBaseUrl(): string {
  // Browser requests go through the Next.js same-origin rewrite, avoiding CORS
  // and localhost resolving to the wrong device when opened over the LAN.
  if (typeof window !== 'undefined') return window.location.origin;

  // Server-side callers use the configured backend directly.
  return process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
}

export function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (typeof item === 'string') return item;
      if (!item || typeof item !== 'object') return '';
      const error = item as { loc?: unknown[]; msg?: unknown; message?: unknown };
      const location = Array.isArray(error.loc) ? error.loc.filter((part) => part !== 'body').join(' > ') : '';
      const message = typeof error.msg === 'string' ? error.msg : typeof error.message === 'string' ? error.message : '';
      return message ? (location ? `${location}: ${message}` : message) : '';
    }).filter(Boolean);
    if (messages.length) return messages.join('; ');
  }
  if (detail && typeof detail === 'object') {
    const error = detail as { message?: unknown; error?: unknown; detail?: unknown; request_id?: unknown };
    for (const candidate of [error.message, error.error, error.detail]) {
      if (typeof candidate === 'string' && candidate.trim()) return typeof error.request_id === 'string' ? `${candidate} (Reference: ${error.request_id})` : candidate;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

function backendNetworkError(error: unknown, baseUrl: string): string {
  const message = error instanceof Error ? error.message : '';
  if (message === 'Failed to fetch' || message.includes('NetworkError')) {
    return `Cannot reach the ClaimWise API at ${baseUrl}. Check that the backend is running and that this address is reachable from your browser.`;
  }
  return message || 'The request could not reach the ClaimWise API.';
}

function authNetworkError(error: unknown): string {
  const message = error instanceof Error ? error.message : '';
  if (message === 'Failed to fetch' || message.includes('NetworkError')) {
    return 'ClaimWise could not reach its server. Start the backend with “npm run backend”, then try again.';
  }
  return message || 'Authentication failed because of a network error.';
}

let _inMemoryCsrfToken: string | null = null;

export function getCsrfToken(): string | null {
  if (typeof document !== 'undefined') {
    const match = document.cookie.match(new RegExp('(^|;\\s*)claimwise_csrf_token=([^;]*)'));
    if (match) return decodeURIComponent(match[2]);
  }
  return _inMemoryCsrfToken;
}

export function setCsrfToken(token: string | null): void {
  _inMemoryCsrfToken = token;
}

export function getStoredAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    // Actively purge any legacy token stored in localStorage
    if (localStorage.getItem('claimwise_auth_token')) {
      localStorage.removeItem('claimwise_auth_token');
    }
  } catch {
    // Ignore localStorage access errors in restricted contexts
  }
  return null;
}

export function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extraHeaders };
  const csrf = getCsrfToken();
  if (csrf && !headers['X-CSRF-Token']) {
    headers['X-CSRF-Token'] = csrf;
  }
  return headers;
}

export async function secureFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const options: RequestInit = { ...init, credentials: 'include' };
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    let csrf = getCsrfToken();
    if (!csrf && typeof window !== 'undefined') {
      try {
        const res = await fetch(`${getBackendBaseUrl()}/api/v1/auth/csrf`, { method: 'GET', credentials: 'include' });
        if (res.ok) {
          const json = await res.json();
          if (json.csrf_token) {
            _inMemoryCsrfToken = json.csrf_token;
            csrf = json.csrf_token;
          }
        }
      } catch {
        // Proceed even if background csrf retrieval fails
      }
    }
    if (csrf && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrf);
    }
  }
  options.headers = headers;
  return fetch(input, options);
}

export async function fetchHealth(): Promise<{ data: HealthResponse | null; latencyMs: number; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  const startTime = performance.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const res = await secureFetch(`${baseUrl}/api/v1/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
      cache: 'no-store',
    });

    clearTimeout(timeoutId);
    const latencyMs = Math.round(performance.now() - startTime);

    if (!res.ok) {
      return {
        data: null,
        latencyMs,
        error: `HTTP ${res.status}: ${res.statusText}`,
      };
    }

    const data: HealthResponse = await res.json();
    return { data, latencyMs, error: null };
  } catch (err: unknown) {
    const latencyMs = Math.round(performance.now() - startTime);
    const message = err instanceof Error ? err.message : 'Failed to reach backend';
    return { data: null, latencyMs, error: message };
  }
}

export async function fetchReadiness(): Promise<{ data: ReadinessResponse | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const res = await secureFetch(`${baseUrl}/api/v1/ready`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
      cache: 'no-store',
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: ReadinessResponse = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to retrieve subsystem readiness';
    return { data: null, error: message };
  }
}

export async function uploadPolicyFile(
  file: File
): Promise<{ data: PolicyExtractionResult | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const formData = new FormData();
    formData.append('file', file);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout for large uploads

    const res = await secureFetch(`${baseUrl}/api/v1/policies/upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back to status text
      }
      return { data: null, error: errorDetail };
    }

    const data: PolicyExtractionResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    let message = err instanceof Error ? err.message : 'Upload failed due to network connection error.';
    if (message === 'Failed to fetch') {
      message = `Cannot reach ClaimWise backend server at ${baseUrl}. Please ensure the backend is running (port 8000).`;
    }
    return { data: null, error: message };
  }
}

export async function fetchUploadedPolicies(): Promise<{
  data: PolicyExtractionResult[] | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/policies`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        errorDetail = formatApiErrorDetail(
          errJson?.detail ?? errJson?.message ?? errJson?.error,
          errorDetail,
        );
      } catch {
        // Fall back to the HTTP status when the response is not JSON.
      }
      return { data: null, error: errorDetail };
    }

    const data: PolicyExtractionResult[] = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    return { data: null, error: backendNetworkError(err, baseUrl) };
  }
}

export async function rewritePolicyHeadings(
  headings: { id: string; heading: string; context: string }[]
): Promise<{ data: { headings: Record<string, string>; ai_used: boolean } | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/policies/headings/rewrite`, {
      method: 'POST',
      headers: getAuthHeaders({ Accept: 'application/json', 'Content-Type': 'application/json' }),
      body: JSON.stringify({ headings }),
    });
    if (!res.ok) return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    return { data: await res.json(), error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unable to generate policy headings.';
    return { data: null, error: message };
  }
}

export async function fetchOriginalPolicyPdf(policyId: string): Promise<{ data: Blob | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/policies/${encodeURIComponent(policyId)}/pdf`, {
      headers: getAuthHeaders({ Accept: 'application/pdf' }),
      cache: 'no-store',
    });
    if (!res.ok) {
      let error = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const body = await res.json();
        if (typeof body.detail === 'string') error = body.detail;
      } catch {
        // The server may return a non-JSON error.
      }
      if (res.status === 404 && error === 'Not Found') {
        error = 'No saved copy of this original PDF was found. Choose the PDF you uploaded to preview it.';
      }
      return { data: null, error };
    }
    return { data: await res.blob(), error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unable to load the original PDF.';
    return { data: null, error: message };
  }
}

export async function calculateCostSharing(
  input: CostCalculationInput
): Promise<{ data: CostCalculationResult | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/rules/calculate`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
      body: JSON.stringify(input),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: CostCalculationResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Rules calculation request failed.';
    return { data: null, error: message };
  }
}

export function dollarsToCentsClient(dollars: number | string): number {
  const parsed = typeof dollars === 'string' ? parseFloat(dollars) : dollars;
  if (isNaN(parsed) || parsed < 0) return 0;
  return Math.round(parsed * 100);
}

export function centsToDollarsClient(cents: number): string {
  if (cents < 0) return `-$${(Math.abs(cents) / 100).toFixed(2)}`;
  return `$${(cents / 100).toFixed(2)}`;
}

export async function askPolicyQuestion(
  request: QARequest
): Promise<{ data: QAResponse | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/qa/ask`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back to status text
      }
      return { data: null, error: errorDetail };
    }

    const data: QAResponse = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Network failure during QA inquiry.';
    return { data: null, error: message };
  }
}

export async function fetchQAPipelineStatus(): Promise<{
  data: QAPipelineStatus | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/qa/status`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: QAPipelineStatus = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch QA pipeline status.';
    return { data: null, error: message };
  }
}

export async function uploadMedicalBill(
  file: File
): Promise<{ data: BillExtractionResult | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const formData = new FormData();
    formData.append('file', file);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    const res = await secureFetch(`${baseUrl}/api/v1/claims/upload-bill`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: BillExtractionResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Medical bill upload network failed.';
    return { data: null, error: message };
  }
}

export async function createClaimFromBill(
  policyId: string,
  billId: string,
  lineItems?: BillLineItem[]
): Promise<{ data: ClaimRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
      body: JSON.stringify({
        policy_id: policyId,
        bill_id: billId,
        line_items: lineItems,
      }),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: ClaimRecord = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to create claim record.';
    return { data: null, error: message };
  }
}

export async function fetchClaims(): Promise<{
  data: ClaimRecord[] | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: ClaimRecord[] = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to retrieve claims.';
    return { data: null, error: message };
  }
}

export async function createClaimIntake(
  payload: ClaimIntakePayload
): Promise<{ data: ClaimRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/intake`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let error = `HTTP ${res.status}: ${res.statusText}`;
      try { error = formatApiErrorDetail((await res.json())?.detail, error); } catch { /* use status */ }
      return { data: null, error };
    }
    return { data: await res.json() as ClaimRecord, error: null };
  } catch (err: unknown) {
    return { data: null, error: err instanceof Error ? err.message : 'Could not create claim draft.' };
  }
}

export async function updateClaimIntake(
  claimId: string,
  payload: Omit<Partial<Pick<ClaimIntakePayload, 'claim_type' | 'incident_description' | 'incident_date' | 'incident_location' | 'estimated_loss_cents' | 'claim_reference'>>, 'incident_location' | 'claim_reference'> & { incident_location?: string | null; claim_reference?: string | null; checklist?: ClaimChecklistItem[]; claim_description_draft?: string }
): Promise<{ data: ClaimRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${encodeURIComponent(claimId)}/intake`, {
      method: 'PATCH',
      headers: getAuthHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let error = `HTTP ${res.status}: ${res.statusText}`;
      try { error = formatApiErrorDetail((await res.json())?.detail, error); } catch { /* use status */ }
      return { data: null, error };
    }
    return { data: await res.json() as ClaimRecord, error: null };
  } catch (err: unknown) {
    return { data: null, error: err instanceof Error ? err.message : 'Could not update claim draft.' };
  }
}

export async function uploadClaimDocument(
  claimId: string,
  file: File
): Promise<{ data: ClaimRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${encodeURIComponent(claimId)}/documents`, {
      method: 'POST', headers: getAuthHeaders({ Accept: 'application/json' }), body: formData,
    });
    if (!res.ok) {
      let error = `HTTP ${res.status}: ${res.statusText}`;
      try { error = formatApiErrorDetail((await res.json())?.detail, error); } catch { /* use status */ }
      return { data: null, error };
    }
    return { data: await res.json() as ClaimRecord, error: null };
  } catch (err: unknown) {
    return { data: null, error: err instanceof Error ? err.message : 'Could not upload claim evidence.' };
  }
}

export async function downloadClaimDocument(
  claimId: string,
  documentId: string
): Promise<{ data: Blob | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${encodeURIComponent(claimId)}/documents/${encodeURIComponent(documentId)}`, {
      headers: getAuthHeaders({ Accept: '*/*' }),
    });
    if (!res.ok) return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    return { data: await res.blob(), error: null };
  } catch (err: unknown) {
    return { data: null, error: err instanceof Error ? err.message : 'Could not download claim evidence.' };
  }
}

export async function fetchClaimById(
  claimId: string
): Promise<{ data: ClaimRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: ClaimRecord = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to retrieve claim details.';
    return { data: null, error: message };
  }
}

export async function adjudicateClaim(
  claimId: string,
  coinsurancePct: number = 20.0,
  deductibleCents?: number,
  oopMaxCents?: number
): Promise<{ data: ExplanationOfBenefits | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/adjudicate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        member_coinsurance_percentage: coinsurancePct,
        initial_remaining_deductible_cents: deductibleCents,
        initial_remaining_oop_max_cents: oopMaxCents,
      }),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: ExplanationOfBenefits = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Adjudication request failed.';
    return { data: null, error: message };
  }
}

export async function submitClaimToSandbox(
  claimId: string,
  scenario: string = 'auto'
): Promise<{ data: SandboxPayerOutcome | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const idempotencyKey = `idemp-${claimId}-${Date.now()}`;
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/sandbox-submit`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
      body: JSON.stringify({
        user_confirmed: true,
        idempotency_key: idempotencyKey,
        requested_scenario: scenario,
      }),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: SandboxPayerOutcome = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Sandbox submission request failed.';
    return { data: null, error: message };
  }
}

// ==============================================================================
// MULTI-POLICY COMPARISON API CLIENTS (MILESTONE 5)
// ==============================================================================

export async function createPolicyComparison(
  payload: ComparisonCreateRequest
): Promise<{ data: ComparisonRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/comparisons`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: ComparisonRecord = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Policy comparison creation failed.';
    return { data: null, error: message };
  }
}

export async function fetchComparisonById(
  comparisonId: string
): Promise<{ data: ComparisonRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/comparisons/${comparisonId}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: ComparisonRecord = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to retrieve comparison.';
    return { data: null, error: message };
  }
}

export async function simulateComparisonCost(
  comparisonId: string,
  assumptions: CostSimulationAssumption
): Promise<{ data: ComparisonCostSimulation | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/comparisons/${comparisonId}/simulate-cost`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(assumptions),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: ComparisonCostSimulation = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Cost simulation recalculation failed.';
    return { data: null, error: message };
  }
}

export async function listComparisons(): Promise<{
  data: ComparisonRecord[] | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/comparisons`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: ComparisonRecord[] = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to list comparisons.';
    return { data: null, error: message };
  }
}

// ==============================================================================
// EVIDENCE-BASED DENIAL APPEAL API CLIENTS (MILESTONE 5)
// ==============================================================================

export async function generateAppealDraft(
  claimId: string,
  payload?: AppealDraftCreateRequest
): Promise<{ data: ClaimAppealDraft | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: ClaimAppealDraft = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Appeal draft generation failed.';
    return { data: null, error: message };
  }
}

export async function fetchAppealDraft(
  claimId: string
): Promise<{ data: ClaimAppealDraft | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: ClaimAppealDraft = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch appeal draft.';
    return { data: null, error: message };
  }
}

export async function updateAppealDraft(
  claimId: string,
  payload: AppealDraftUpdateRequest
): Promise<{ data: ClaimAppealDraft | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: ClaimAppealDraft = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to update appeal draft.';
    return { data: null, error: message };
  }
}

export async function exportAppealPackage(
  claimId: string
): Promise<{ data: AppealExportPackage | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: AppealExportPackage = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to export appeal package.';
    return { data: null, error: message };
  }
}

function triggerBrowserDownload(blob: Blob, fallbackFilename: string, contentDisposition?: string | null) {
  let filename = fallbackFilename;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) {
      filename = match[1].trim();
    }
  }
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export async function downloadClaimEobPdf(
  claimId: string,
  fallbackFilename = `ClaimWise_EOB_${claimId.slice(0, 8)}.pdf`
): Promise<{ success: boolean; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/eob/pdf`, {
      method: 'GET',
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) errorDetail = errorJson.detail;
      } catch {
        // Fall back
      }
      return { success: false, error: errorDetail };
    }
    const blob = await res.blob();
    triggerBrowserDownload(blob, fallbackFilename, res.headers.get('Content-Disposition'));
    return { success: true, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to download EOB PDF.';
    return { success: false, error: message };
  }
}

export async function downloadAppealPdf(
  claimId: string,
  fallbackFilename = `ClaimWise_Appeal_${claimId.slice(0, 8)}.pdf`
): Promise<{ success: boolean; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft/pdf`, {
      method: 'GET',
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) errorDetail = errorJson.detail;
      } catch {
        // Fall back
      }
      return { success: false, error: errorDetail };
    }
    const blob = await res.blob();
    triggerBrowserDownload(blob, fallbackFilename, res.headers.get('Content-Disposition'));
    return { success: true, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to download Appeal PDF.';
    return { success: false, error: message };
  }
}

export async function downloadComparisonPdf(
  comparisonId: string,
  fallbackFilename = `ClaimWise_Comparison_${comparisonId.slice(0, 8)}.pdf`
): Promise<{ success: boolean; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/comparisons/${comparisonId}/pdf`, {
      method: 'GET',
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) errorDetail = errorJson.detail;
      } catch {
        // Fall back
      }
      return { success: false, error: errorDetail };
    }
    const blob = await res.blob();
    triggerBrowserDownload(blob, fallbackFilename, res.headers.get('Content-Disposition'));
    return { success: true, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to download Comparison PDF.';
    return { success: false, error: message };
  }
}

export async function fetchAuditEvents(params?: {
  action?: string;
  resource_type?: string;
  resource_id?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
}): Promise<{ data: AuditEvent[] | null; total: number; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  const searchParams = new URLSearchParams();
  if (params?.action) searchParams.append('action', params.action);
  if (params?.resource_type) searchParams.append('resource_type', params.resource_type);
  if (params?.resource_id) searchParams.append('resource_id', params.resource_id);
  if (params?.outcome) searchParams.append('outcome', params.outcome);
  if (params?.limit) searchParams.append('limit', String(params.limit));
  if (params?.offset !== undefined) searchParams.append('offset', String(params.offset));

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/audit/events?${searchParams.toString()}`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, total: 0, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const totalHeader = res.headers.get('x-total-count');
    const data: AuditEvent[] = await res.json();
    const total = totalHeader ? parseInt(totalHeader, 10) : data.length;
    return { data, total, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch audit events.';
    return { data: null, total: 0, error: message };
  }
}

export async function verifyAuditChain(): Promise<{
  data: AuditVerificationResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/audit/verify`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        errorDetail = formatApiErrorDetail(errJson?.detail ?? errJson?.message ?? errJson?.error, errorDetail);
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: AuditVerificationResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to verify cryptographic audit trail.';
    return { data: null, error: message };
  }
}

export async function fetchQABenchmark(params?: {
  live?: boolean;
  max_questions?: number;
}): Promise<{
  data: BenchmarkExecutionReport | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  const searchParams = new URLSearchParams();
  if (params?.live !== undefined) searchParams.append('live', String(params.live));
  if (params?.max_questions) searchParams.append('max_questions', String(params.max_questions));

  try {
    const res = await secureFetch(`${baseUrl}/api/v1/qa/benchmark?${searchParams.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorDetail = errJson.detail;
      } catch {
        // Fall back
      }
      return { data: null, error: errorDetail };
    }

    const data: BenchmarkExecutionReport = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to execute Q&A benchmark suite.';
    return { data: null, error: message };
  }
}

export async function fetchCoveragePresets(): Promise<{
  data: PresetScenarioItem[] | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/coverage/presets`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data: PresetScenarioItem[] = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    return { data: null, error: backendNetworkError(err, baseUrl) };
  }
}

export async function analyzeCoverageScenario(
  payload: CoverageScenarioRequest
): Promise<{
  data: CoverageGapAnalysisResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/coverage/analyze`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        errorDetail = formatApiErrorDetail(errJson?.detail ?? errJson?.message ?? errJson?.error, errorDetail);
      } catch {
        // fallback
      }
      return { data: null, error: errorDetail };
    }
    const data: CoverageGapAnalysisResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    return { data: null, error: backendNetworkError(err, baseUrl) };
  }
}

export async function fetchPolicyCoverageReport(
  policyId: string
): Promise<{
  data: CoverageGapReportResponse | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/coverage/report/${encodeURIComponent(policyId)}`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        errorDetail = formatApiErrorDetail(
          errJson?.detail ?? errJson?.message ?? errJson?.error,
          errorDetail,
        );
      } catch {
        // fallback
      }
      return { data: null, error: errorDetail };
    }
    const data: CoverageGapReportResponse = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    return { data: null, error: backendNetworkError(err, baseUrl) };
  }
}

export async function fetchGuidanceQuestions(): Promise<{
  data: IncidentQuestionnaireSchema | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/guidance/questions`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }
    const data: IncidentQuestionnaireSchema = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch guidance questionnaire schema.';
    return { data: null, error: message };
  }
}

export async function evaluateIncidentGuidance(
  payload: IncidentQuestionnaireRequest
): Promise<{
  data: IncidentGuidanceResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/guidance/evaluate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorDetail = errJson.detail;
      } catch {
        // fallback
      }
      return { data: null, error: errorDetail };
    }
    const data: IncidentGuidanceResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to evaluate incident guidance.';
    return { data: null, error: message };
  }
}

export async function fetchClaimGuidance(
  claimId: string
): Promise<{
  data: IncidentGuidanceResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/claims/${encodeURIComponent(claimId)}/guidance`, {
      method: 'GET',
      headers: getAuthHeaders({ Accept: 'application/json' }),
      cache: 'no-store',
    });
    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorDetail = errJson.detail;
      } catch {
        // fallback
      }
      return { data: null, error: errorDetail };
    }
    const data: IncidentGuidanceResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch claim guidance.';
    return { data: null, error: message };
  }
}

// ==============================================================================
// F4: AGGREGATE PORTFOLIO MANAGEMENT & COB OPTIMIZER API CLIENTS
// ==============================================================================

export async function analyzePortfolio(
  payload: PortfolioAnalysisRequest
): Promise<{
  data: PortfolioAnalysisResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/portfolio/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorDetail = errJson.detail;
      } catch {
        // fallback
      }
      return { data: null, error: errorDetail };
    }

    const data: PortfolioAnalysisResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to analyze portfolio.';
    return { data: null, error: message };
  }
}

export async function getSamplePortfolioAnalysis(
  patientRelationship: string = 'policyholder'
): Promise<{
  data: PortfolioAnalysisResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(
      `${baseUrl}/api/v1/portfolio/sample?patient_relationship=${encodeURIComponent(patientRelationship)}`,
      {
        method: 'GET',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      }
    );

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorDetail = errJson.detail;
      } catch {
        // fallback
      }
      return { data: null, error: errorDetail };
    }

    const data: PortfolioAnalysisResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load sample portfolio analysis.';
    return { data: null, error: message };
  }
}

export async function getCOBRulesReference(): Promise<{
  data: Record<string, unknown> | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/portfolio/rules`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: Record<string, unknown> = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch COB rules reference.';
    return { data: null, error: message };
  }
}

// ---------------------------------------------------------------------------
// Authentication Helpers & Client Services
// ---------------------------------------------------------------------------


export function setStoredAuth(_token: string, user: AuthUser): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem('claimwise_auth_token');
    localStorage.setItem(
      'claimwise_user_profile',
      JSON.stringify({
        fullName: user.full_name,
        email: user.email,
        id: user.id,
      })
    );
    window.dispatchEvent(new Event('claimwise_profile_updated'));
  } catch (err) {
    console.error('Failed to persist auth session:', err);
  }
}

export function clearStoredAuth(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem('claimwise_auth_token');
    localStorage.removeItem('claimwise_user_profile');
    _inMemoryCsrfToken = null;
    window.dispatchEvent(new Event('claimwise_profile_updated'));
  } catch (err) {
    console.error('Failed to clear auth session:', err);
  }
}

export async function loginUser(
  payload: LoginPayload
): Promise<{ data: AuthResponse | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {
        // Fall back
      }
      return { data: null, error: detail };
    }

    const data: AuthResponse = await res.json();
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }
    setStoredAuth(data.access_token, data.user);
    return { data, error: null };
  } catch (err: unknown) {
    return { data: null, error: authNetworkError(err) };
  }
}

export async function signupUser(
  payload: SignUpPayload
): Promise<{ data: AuthResponse | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/auth/signup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {
        // Fall back
      }
      return { data: null, error: detail };
    }

    const data: AuthResponse = await res.json();
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }
    setStoredAuth(data.access_token, data.user);
    return { data, error: null };
  } catch (err: unknown) {
    return { data: null, error: authNetworkError(err) };
  }
}

export async function updateAccountProfile(payload: { full_name: string; address: string }): Promise<{ data: AuthUser | null; error: string | null }> {
  try {
    const res = await secureFetch(`${getBackendBaseUrl()}/api/v1/auth/profile`, {
      method: 'PUT',
      headers: getAuthHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      return { data: null, error: body?.detail || `HTTP ${res.status}: ${res.statusText}` };
    }
    const data: AuthUser = await res.json();
    try {
      const stored = JSON.parse(localStorage.getItem('claimwise_user_profile') || '{}');
      localStorage.setItem('claimwise_user_profile', JSON.stringify({ ...stored, id: data.id, email: data.email, fullName: data.full_name, address: data.address || '' }));
      window.dispatchEvent(new Event('claimwise_profile_updated'));
    } catch { /* Keep the successful server update even if local storage is unavailable. */ }
    return { data, error: null };
  } catch (error) {
    return { data: null, error: authNetworkError(error) };
  }
}

export async function changeAccountPassword(payload: { current_password: string; new_password: string }): Promise<{ error: string | null }> {
  try {
    const res = await secureFetch(`${getBackendBaseUrl()}/api/v1/auth/password`, {
      method: 'PUT',
      headers: getAuthHeaders({ 'Content-Type': 'application/json', Accept: 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      return { error: body?.detail || `HTTP ${res.status}: ${res.statusText}` };
    }
    return { error: null };
  } catch (error) {
    return { error: authNetworkError(error) };
  }
}

export async function demoLoginUser(
  payload: DemoLoginPayload
): Promise<{ data: AuthResponse | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/auth/demo`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) detail = errJson.detail;
      } catch {
        // Fall back
      }
      return { data: null, error: detail };
    }

    const data: AuthResponse = await res.json();
    if (data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }
    setStoredAuth(data.access_token, data.user);
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Demo sign in failed.';
    return { data: null, error: message };
  }
}

export async function fetchCurrentUser(): Promise<{
  data: AuthUser | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();
  try {
    const res = await secureFetch(`${baseUrl}/api/v1/auth/me`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      if (res.status === 401) {
        clearStoredAuth();
        return { data: null, error: null };
      }
      return { data: null, error: `HTTP ${res.status}` };
    }

    const data: AuthUser = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch current user profile.';
    return { data: null, error: message };
  }
}

export async function logoutUser(): Promise<{ error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  try {
    await secureFetch(`${baseUrl}/api/v1/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders({
        Accept: 'application/json',
      }),
    });
  } catch {
    // Ignore network error on logout
  } finally {
    clearStoredAuth();
  }
  return { error: null };
}



