import {build, context} from "esbuild";
import {watch as watchFile} from "node:fs";
import {copyFile, mkdir, readFile, writeFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(root, "./static");
const watchMode = process.argv.includes("--watch");
const dashboardHtml = path.join(output, "index.html");
async function writeDashboardHtml() {
  const html = await readFile(path.join(root, "index.html"), "utf8");
  const version = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const marker = `<meta name="guardian-build-version" content="${version}">`;
  await writeFile(dashboardHtml, html.replace("</head>", `  ${marker}\n</head>`), "utf8");
}
await mkdir(output, {recursive: true});
if (!watchMode) await copyFile(path.join(root, "index.html"), dashboardHtml);
await copyFile(path.join(root, "service-worker.js"), path.join(output, "service-worker.js"));
const options = {
  entryPoints: [path.join(root, "src/main.jsx")],
  outfile: path.join(output, "app.js"),
  bundle: true, minify: true, jsx: "automatic", charset: "ascii",
  define: {"process.env.NODE_ENV": JSON.stringify(watchMode ? "development" : "production")},
  logLevel: "info", legalComments: "eof",
  plugins: watchMode ? [{
    name: "guardian-dashboard-build-marker",
    setup(build) {
      build.onEnd(async (result) => {
        if (result.errors.length === 0) await writeDashboardHtml();
      });
    }
  }] : []
};
if (watchMode) {
  await writeDashboardHtml();
  const watcher = await context(options);
  await watcher.watch();
  let serviceWorkerCopyTimer;
  const serviceWorkerWatcher = watchFile(path.join(root, "service-worker.js"), () => {
    clearTimeout(serviceWorkerCopyTimer);
    serviceWorkerCopyTimer = setTimeout(async () => {
      try {
        await copyFile(path.join(root, "service-worker.js"), path.join(output, "service-worker.js"));
        await writeDashboardHtml();
        console.log("Updated service worker; dashboard will reload to activate it.");
      } catch (error) {
        console.error("Could not update Guardian service worker:", error.message);
      }
    }, 100);
  });
  process.on("exit", () => serviceWorkerWatcher.close());
  console.log("Watching React source. The connected Guardian dashboard will reload after each successful build; keep the Python gateway running.");
} else {
  await build(options);
}

