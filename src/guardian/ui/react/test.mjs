import {build} from "esbuild";
import {fileURLToPath} from "node:url";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.dirname(fileURLToPath(import.meta.url));
const target = path.join(root, ".test-build/components.test.cjs");
await build({entryPoints: [path.join(root, "tests/components.test.jsx")], outfile: target,
  bundle: true, platform: "node", format: "cjs", jsx: "automatic",
  define: {"process.env.NODE_ENV": '"production"'}});
const result = spawnSync(process.execPath, ["--test", target, path.join(root, "tests/service-worker.test.mjs")], {stdio: "inherit"});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
