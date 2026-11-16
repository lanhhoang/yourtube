import createClient from "openapi-fetch";
import type { paths } from "./api.gen.ts";
import { ApiError } from "./errors.ts";

export const api = createClient<paths>({ baseUrl: "" });

type Result<T> = { data?: T; error?: unknown; response: Response };

function errorFrom(error: unknown): ApiError {
  const body = (error as { error?: { code?: unknown; message?: unknown } } | null)?.error;
  const code = typeof body?.code === "string" ? body.code : "unknown";
  const message = typeof body?.message === "string" ? body.message : "Something went wrong.";
  return new ApiError(code, message);
}

export async function call<T>(p: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await p;
  } catch {
    throw new ApiError("network", "Can't reach the server.");
  }
  if (result.error !== undefined) throw errorFrom(result.error);
  return result.data as T;
}
