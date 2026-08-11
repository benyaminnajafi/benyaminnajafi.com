// @ts-check
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://benyaminnajafi.com",
  // Static output, and no UI framework: every component below compiles to a
  // string at build time. The three interactive behaviours are hand-written
  // scripts, so nothing ships a runtime.
  output: "static",
  build: {
    // One <style> in the head instead of a request. The whole stylesheet is a
    // few KB — a separate file would cost more in latency than it saves.
    inlineStylesheets: "always",
  },
  markdown: {
    // Off deliberately: smartypants rewrites ' as ’ and " as “ ”, which
    // silently changes the author's text. The reference renders straight
    // quotes, and a rebuild that "improves" the copy is a rebuild that no
    // longer matches it.
    smartypants: false,
  },
  devToolbar: { enabled: false },
});
