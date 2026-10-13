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
} from '@/types/api';


export function getBackendBaseUrl(): string {
  // Configurable backend URL via NEXT_PUBLIC_API_URL or fallback to local port 8000
  return process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
}

export async function fetchHealth(): Promise<{ data: HealthResponse | null; latencyMs: number; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  const startTime = performance.now();

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const res = await fetch(`${baseUrl}/api/v1/health`, {
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

    const res = await fetch(`${baseUrl}/api/v1/ready`, {
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

    const res = await fetch(`${baseUrl}/api/v1/policies/upload`, {
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
        // Fall back to status text
      }
      return { data: null, error: errorDetail };
    }

    const data: PolicyExtractionResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Upload failed due to network connection error.';
    return { data: null, error: message };
  }
}

export async function fetchUploadedPolicies(): Promise<{
  data: PolicyExtractionResult[] | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await fetch(`${baseUrl}/api/v1/policies`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: PolicyExtractionResult[] = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to retrieve policy list.';
    return { data: null, error: message };
  }
}

export async function calculateCostSharing(
  input: CostCalculationInput
): Promise<{ data: CostCalculationResult | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await fetch(`${baseUrl}/api/v1/rules/calculate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
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
    const res = await fetch(`${baseUrl}/api/v1/qa/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
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
    const res = await fetch(`${baseUrl}/api/v1/qa/status`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
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

    const res = await fetch(`${baseUrl}/api/v1/claims/upload-bill`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
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
    const res = await fetch(`${baseUrl}/api/v1/claims`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
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

export async function fetchClaimById(
  claimId: string
): Promise<{ data: ClaimRecord | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/adjudicate`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/sandbox-submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
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
    const res = await fetch(`${baseUrl}/api/v1/comparisons`, {
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
    const res = await fetch(`${baseUrl}/api/v1/comparisons/${comparisonId}`, {
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
    const res = await fetch(`${baseUrl}/api/v1/comparisons/${comparisonId}/simulate-cost`, {
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
    const res = await fetch(`${baseUrl}/api/v1/comparisons`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft/export`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/eob/pdf`, {
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
    const res = await fetch(`${baseUrl}/api/v1/claims/${claimId}/appeal-draft/pdf`, {
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
    const res = await fetch(`${baseUrl}/api/v1/comparisons/${comparisonId}/pdf`, {
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
  limit?: number;
}): Promise<{ data: AuditEvent[] | null; error: string | null }> {
  const baseUrl = getBackendBaseUrl();
  const searchParams = new URLSearchParams();
  if (params?.action) searchParams.append('action', params.action);
  if (params?.resource_type) searchParams.append('resource_type', params.resource_type);
  if (params?.limit) searchParams.append('limit', String(params.limit));

  try {
    const res = await fetch(`${baseUrl}/api/v1/audit/events?${searchParams.toString()}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });

    if (!res.ok) {
      return { data: null, error: `HTTP ${res.status}: ${res.statusText}` };
    }

    const data: AuditEvent[] = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch audit events.';
    return { data: null, error: message };
  }
}

export async function verifyAuditChain(): Promise<{
  data: AuditVerificationResult | null;
  error: string | null;
}> {
  const baseUrl = getBackendBaseUrl();

  try {
    const res = await fetch(`${baseUrl}/api/v1/audit/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
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

    const data: AuditVerificationResult = await res.json();
    return { data, error: null };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to verify cryptographic audit trail.';
    return { data: null, error: message };
  }
}



