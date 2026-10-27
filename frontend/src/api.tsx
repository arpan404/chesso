import { createContext, useCallback, useContext, type ReactNode } from "react";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
const ApiContext = createContext<Api | null>(null);
export function ApiProvider({
  getToken,
  children,
}: {
  getToken: () => Promise<string | null>;
  children: ReactNode;
}) {
  const api = useCallback<Api>(
    async <T,>(path: string, options: RequestInit = {}) => {
      const token = await getToken();
      if (!token) throw new ApiError("Sign in to continue.", 401);
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || ""}/api${path}`,
        {
          ...options,
          headers: {
            "Content-Type": "application/json",
            ...options.headers,
            Authorization: `Bearer ${token}`,
          },
        },
      );
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        const detail =
          typeof error.detail === "string"
            ? error.detail
            : "Check your entry and try again.";
        throw new ApiError(detail, response.status);
      }
      if (response.status === 204) return undefined as T;
      if (path.endsWith("/export")) return (await response.blob()) as T;
      return (await response.json()) as T;
    },
    [getToken],
  );
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}
export function useApi() {
  const value = useContext(ApiContext);
  if (!value) throw new Error("The chess workspace needs ApiProvider.");
  return value;
}
export const jsonRequest = (body: unknown, method = "POST"): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
