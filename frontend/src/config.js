// API Configuration
// Dynamically set based on environment

const getApiUrl = () => {
  // For web (React web version)
  if (typeof window !== "undefined") {
    return process.env.REACT_APP_API_URL || "https://api.acty-labs.com";
  }
  // For React Native
  return process.env.REACT_APP_API_URL || "http://192.168.68.138:8765";
};

export const API_BASE = getApiUrl();

// API Endpoints
export const API_ENDPOINTS = {
  HEALTH: `${API_BASE}/health`,
  INSIGHTS: `${API_BASE}/insights`,
  EARLY_ACCESS: `${API_BASE}/api/early-access`,
  LLM_CONFIG: `${API_BASE}/api/v1/llm-config`,
  CDR: `${API_BASE}/cdr`,
  ANOMALIES: `${API_BASE}/anomalies`,
};

// Export for logging/debugging
export const getApiConfig = () => ({
  apiBase: API_BASE,
  endpoints: API_ENDPOINTS,
  environment: process.env.NODE_ENV || "development",
  envApiUrl: process.env.REACT_APP_API_URL,
});

export default {
  API_BASE,
  API_ENDPOINTS,
  getApiConfig,
};
