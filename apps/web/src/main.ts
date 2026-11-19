import "./share-redirect.ts"; // first: it must run before the router reads location.hash
import "@fontsource-variable/inter";
import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";

mount(App, { target: document.getElementById("app") as HTMLElement });
