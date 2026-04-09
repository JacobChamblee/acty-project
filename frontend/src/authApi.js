import { API_BASE } from './config';

function parseError(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}

function normalizeAccountResponse(payload = {}) {
  const account = payload.account || {};
  const email = (account.email || payload.email || '').toLowerCase();
  const passwordHash = payload.password_hash || account._pwHash || account.pwHash || '';
  return {
    ...account,
    email,
    ...(passwordHash ? { _pwHash: passwordHash } : {}),
  };
}

async function postJson(path, body, fallbackMessage) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (!response.ok) {
    throw new Error(parseError(payload.detail, fallbackMessage));
  }
  return payload;
}

export async function syncRemoteAccount(account) {
  if (!account?.email) return account;
  try {
    const payload = await postJson(
      '/api/v1/auth/sync',
      {
        email: account.email.toLowerCase(),
        password_hash: account._pwHash || account.pwHash || null,
        account,
      },
      'Could not sync account.',
    );
    return normalizeAccountResponse(payload);
  } catch {
    return account;
  }
}

export async function loginRemoteAccount(email, passwordHash) {
  const payload = await postJson(
    '/api/v1/auth/login',
    {
      email: email.toLowerCase(),
      password_hash: passwordHash,
    },
    'Could not sign in.',
  );
  return normalizeAccountResponse(payload);
}

export async function registerRemoteAccount(account) {
  const payload = await postJson(
    '/api/v1/auth/register',
    {
      email: account.email.toLowerCase(),
      password_hash: account._pwHash || account.pwHash || null,
      account,
    },
    'Could not create account.',
  );
  return normalizeAccountResponse(payload);
}
