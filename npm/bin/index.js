#!/usr/bin/env node

/**
 * Book Recommendations MCP Server NPX Wrapper
 * Spawns the python package via uvx with full stdio passthrough for MCP hosts.
 */

const { spawn } = require('child_process');

const args = ['--from', 'book-recommendations', 'book-recommendations-server', ...process.argv.slice(2)];

const child = spawn('uvx', args, {
  stdio: 'inherit',
  shell: process.platform === 'win32'
});

child.on('error', (err) => {
  if (err.code === 'ENOENT') {
    console.error('[book-recommendations Error] "uvx" command not found.');
    console.error('Please install uv (https://astral.sh/uv) or install directly via pip: pip install book-recommendations');
  } else {
    console.error('[book-recommendations Error] Failed to start server process:', err.message);
  }
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code || 0);
});
