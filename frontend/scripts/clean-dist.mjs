import { rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const outputDirectory = resolve(scriptDirectory, '..', 'dist');

// Remove a previous production bundle before typechecking/building so a failed
// build cannot leave a stale UI that start_hsptl.bat might serve accidentally.
await rm(outputDirectory, { recursive: true, force: true });
