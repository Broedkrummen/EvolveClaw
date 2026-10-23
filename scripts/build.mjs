import { build } from 'esbuild';
await build({ entryPoints: ['plugin/src/index.ts'], bundle: true, platform: 'node', format: 'esm', packages: 'external', outfile: 'dist/index.js' });
await build({ entryPoints: ['plugin/src/control-ui.ts'], bundle: true, platform: 'browser', format: 'esm', target: ['es2022'], outfile: 'dist/control-ui/index.js' });
