export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function messageFor(err: unknown): string {
  return err instanceof ApiError && err.message ? err.message : "Something went wrong.";
}
