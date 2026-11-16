export type Route =
  | { name: "library" }
  | { name: "queue" }
  | { name: "settings" }
  | { name: "fetch"; urls: string };

const LIBRARY: Route = { name: "library" };

function decode(s: string): string | null {
  try {
    return decodeURIComponent(s);
  } catch {
    return null;
  }
}

export function parseHash(hash: string): Route {
  const [kind, raw, ...rest] = hash.replace(/^#\/?/, "").split("/");
  if (rest.length > 0) return LIBRARY;
  switch (kind) {
    case "queue":
      return raw === undefined ? { name: "queue" } : LIBRARY;
    case "settings":
      return raw === undefined ? { name: "settings" } : LIBRARY;
    case "fetch": {
      const urls = raw ? decode(raw) : null;
      return urls ? { name: "fetch", urls } : LIBRARY;
    }
    default:
      return LIBRARY;
  }
}

export function href(r: Route): string {
  switch (r.name) {
    case "library":
      return "#/";
    case "fetch":
      return `#/fetch/${encodeURIComponent(r.urls)}`;
    default:
      return `#/${r.name}`;
  }
}

export type Section = "library" | "queue" | "settings" | null;

// Which rail link a route belongs to, for aria-current. A fetch has none.
export function section(r: Route): Section {
  return r.name === "fetch" ? null : r.name;
}
