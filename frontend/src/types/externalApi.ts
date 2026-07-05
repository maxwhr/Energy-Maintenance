export interface ExternalApiProvider {
  id: string
  provider_code: string
  provider_name: string
  provider_type: string
  description?: string | null
  enabled: boolean
  requires_api_key: boolean
  base_url_env_key?: string | null
  api_key_env_key?: string | null
  model_env_key?: string | null
  default_model_name?: string | null
  timeout_seconds: number
  max_tokens?: number | null
  temperature?: number | string | null
  capabilities_json?: string[] | null
  status: string
  status_checked_at?: string | null
  metadata_json?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ExternalApiProviderStatus {
  provider_code: string
  provider_name: string
  provider_type: string
  enabled: boolean
  configured: boolean
  requires_api_key: boolean
  status: string
  status_checked_at?: string | null
  capabilities: string[]
  base_url_configured: boolean
  api_key_configured: boolean
  model_configured: boolean
  model_name?: string | null
  timeout_seconds: number
  message: string
}

export interface ExternalApiRoute {
  id: string
  route_code: string
  agent_code?: string | null
  tool_name?: string | null
  capability: string
  primary_provider_code: string
  fallback_provider_codes_json?: string[] | null
  allow_fallback: boolean
  blocked_when_unconfigured: boolean
  safety_policy_json?: Record<string, unknown> | null
  metadata_json?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ExternalApiStatus {
  providers: ExternalApiProviderStatus[]
  routes: ExternalApiRoute[]
  gateway_mode: string
  real_external_calls_enabled: boolean
}

export interface ExternalApiDryRunPayload {
  capability: string
  provider_code?: string | null
  route_code?: string | null
  agent_code?: string | null
  tool_name?: string | null
  input_summary?: Record<string, unknown>
}

export interface ExternalApiRealRunPayload extends ExternalApiDryRunPayload {
  real_run: true
}

export interface ExternalApiRealCheckPayload {
  provider_code: string
  capability: string
  input_summary?: Record<string, unknown>
  real_run: true
}

export interface ExternalApiGatewayResult {
  trace_id: string
  status: string
  success: boolean
  provider_code?: string | null
  capability: string
  route_code?: string | null
  model_name?: string | null
  would_call: boolean
  external_api_called: boolean
  blocked_reason?: string | null
  message: string
  request_summary: Record<string, unknown>
  response_summary: Record<string, unknown>
  normalized_result: Record<string, unknown>
}

export interface ExternalApiCheckResult extends ExternalApiGatewayResult {
  checked_at: string
}

export interface ExternalApiCallLog {
  id: string
  trace_id: string
  provider_code: string
  capability: string
  agent_run_id?: string | null
  agent_tool_call_id?: string | null
  request_summary_json?: Record<string, unknown> | null
  response_summary_json?: Record<string, unknown> | null
  status: string
  success: boolean
  latency_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  token_usage_json?: Record<string, unknown> | null
  created_by?: string | null
  created_at: string
}

export interface ExternalApiHealthCheck {
  id: string
  provider_code: string
  status: string
  latency_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  checked_at: string
  created_by?: string | null
}
