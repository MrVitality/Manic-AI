#!/usr/bin/env node
/**
 * PreToolUse Hook: Block creation of unnecessary .md/.txt documentation files
 *
 * Prevents creating arbitrary documentation files.
 * Allows: README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md,
 *         files in .claude/plans/, docs/FAQ/, docs/superpowers/
 */

const MAX_STDIN = 1024 * 1024;
let data = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { if (data.length < MAX_STDIN) data += chunk; });
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(data);
    const p = input.tool_input?.file_path || '';
    if (
      /\.(md|txt)$/.test(p) &&
      !/(README|CLAUDE|AGENTS|CONTRIBUTING)\.md$/.test(p) &&
      !/.claude\/plans\//.test(p) &&
      !/docs\/FAQ\//.test(p) &&
      !/docs\/superpowers\//.test(p)
    ) {
      console.error('[Hook] BLOCKED: Unnecessary documentation file creation');
      console.error('[Hook] File: ' + p);
      console.error('[Hook] Use README.md for documentation instead');
      process.exit(2);
    }
  } catch { /* non-JSON or missing field — pass through */ }
  process.stdout.write(data);
  process.exit(0);
});
