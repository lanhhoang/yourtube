import { href, parseHash, type Route } from "./router.ts";

let route = $state<Route>(parseHash(location.hash));
addEventListener("hashchange", () => {
  route = parseHash(location.hash);
});

export const router: { readonly route: Route } = {
  get route() {
    return route;
  },
};

export function navigate(r: Route): void {
  location.hash = href(r);
}
