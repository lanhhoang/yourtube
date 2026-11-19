import { href } from "./lib/router.ts";
import { sharedUrl } from "./lib/share.ts";

// A share target opens `/?share=<url>`. Turn that into `/#/fetch/<url>` before anything
// reads location.hash. main.ts imports this module first, so it runs ahead of the router.
const url = sharedUrl(location.search);
if (url) history.replaceState(null, "", `/${href({ name: "fetch", urls: url })}`);
