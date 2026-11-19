const RELOAD_KEY = "guardian:dev-reload";

if (process.env.NODE_ENV === "development") {
  let currentVersion = null;
  let checking = false;

  async function checkForBuild() {
    if (checking || document.hidden) return;
    checking = true;
    try {
      const response = await fetch("/dashboard/", {cache: "no-store"});
      if (!response.ok) return;
      const html = await response.text();
      const version = html.match(/name="guardian-build-version" content="([^"]+)"/)?.[1];
      if (!version) return;
      if (currentVersion === null) {
        currentVersion = version;
      } else if (version !== currentVersion) {
        sessionStorage.setItem(RELOAD_KEY, "1");
        window.location.reload();
      }
    } catch {
      // The gateway may be starting; a later poll retries without interrupting the app.
    } finally {
      checking = false;
    }
  }

  checkForBuild();
  window.setInterval(checkForBuild, 1000);
}
