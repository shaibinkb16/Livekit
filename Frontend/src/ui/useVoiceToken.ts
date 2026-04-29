import { useCallback, useState } from 'react';

type TokenRequest = {
  room_name?: string;
  participant_name?: string;
  participant_identity?: string;
  participant_metadata?: string;
  participant_attributes?: Record<string, string>;
  agent_name?: string;
  room_config?: Record<string, unknown>;
};

export type TokenResponse = {
  server_url: string;
  participant_token: string;
  room_name: string;
  agent_name: string;
  expires_at?: number;
};

export type TokenError = {
  status?: number;
  message: string;
};

function getBearerHeader() {
  const demo = (import.meta.env.VITE_DEMO_BEARER_TOKEN as string | undefined) ?? 'demo';
  return `Bearer ${demo}`;
}

export function useVoiceToken() {
  const [data, setData] = useState<TokenResponse | undefined>();
  const [error, setError] = useState<TokenError | undefined>();
  const [loading, setLoading] = useState(false);

  const reset = useCallback(() => {
    setData(undefined);
    setError(undefined);
    setLoading(false);
  }, []);

  const requestToken = useCallback(async (req: TokenRequest) => {
    setLoading(true);
    setError(undefined);
    try {
      const res = await fetch('/api/token', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          authorization: getBearerHeader(),
        },
        body: JSON.stringify(req),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => '');
        setError({
          status: res.status,
          message: text || res.statusText || 'Request failed',
        });
        setData(undefined);
        return undefined;
      }

      const json = (await res.json()) as TokenResponse;
      setData(json);
      return json;
    } catch (e) {
      setError({ message: e instanceof Error ? e.message : 'Request failed' });
      setData(undefined);
      return undefined;
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, error, loading, requestToken, reset };
}

