import { defineConfig } from 'astro/config';
import { rmSync } from 'node:fs';
const publish = process.env.PUBLISH === '1';
export default defineConfig({
  vite: {build: {assetsInlineLimit: 0}},
  outDir: publish ? 'dist/production' : 'dist/preview',
  publicDir: publish ? 'site-public' : 'public',
  integrations: [{ name: 'private-review', hooks: {'astro:build:done': ({dir}) => {if(publish) rmSync(new URL('review/',dir),{recursive:true,force:true});}}}]
});
