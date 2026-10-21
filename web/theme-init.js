// Applies a saved light-theme choice before first paint, so the page doesn't
// flash twilight first. It must be a separate file: the production CSP
// (script-src 'self' ...) has no 'unsafe-inline', so an inline <script> here
// is silently blocked -- test_page_boots_under_enforced_csp caught exactly that.
try {
  if (localStorage.getItem("cairn-theme") === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  }
} catch (e) {}
