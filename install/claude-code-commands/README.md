# Real `/ts-*` slash commands for Claude Code

The upstream suite shipped 30 slash commands. Inside the merged skill they are *recipes* the router reads (`commands/`), reachable as `/teaching-skill ts-exam …`. If you also want the short `/ts-exam`-style commands, copy the wrappers in this folder into your Claude Code commands folder:

```
# Windows PowerShell
Copy-Item "<path-to>\teaching-skill\install\claude-code-commands\ts-*.md" "$HOME\.claude\commands\"

# macOS / Linux
cp <path-to>/teaching-skill/install/claude-code-commands/ts-*.md ~/.claude/commands/
```

Each wrapper just hands the request to the `teaching-skill` skill with the right module and mode, so the skill itself must be installed too. They are optional; nothing else depends on them.
