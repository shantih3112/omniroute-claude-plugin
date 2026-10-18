# OmniRoute Claude Code Plugin

Registers [OmniRoute](https://github.com/diegosouzapw/OmniRoute)'s MCP server with Claude
Code, so Claude Code gets OmniRoute's full toolset (routing, providers, combos, cache,
compression, memory) as MCP tools -- without you having to run `claude mcp add-server`
by hand.

This plugin does exactly one thing: it wires up the MCP connection. It does not bundle any
slash commands, agents, hooks, or skills. All of OmniRoute's own functionality (dashboard,
CLI, `omniroute run` / `omniroute configure`) is unaffected and still works the normal way.

## Prerequisites

- An OmniRoute instance already installed and running:

  ```bash
  npm install -g omniroute
  omniroute
  ```

  By default it listens on `http://localhost:20128` and exposes its MCP server at
  `http://localhost:20128/api/mcp/stream`.
- Claude Code with the plugin system available.

## Install

### Option A: local testing (no marketplace)

Point Claude Code straight at this directory:

```bash
claude --plugin-dir /path/to/omniroute-claude-plugin
```

### Option B: as a marketplace

This repo is self-hosting: its `.claude-plugin/marketplace.json` lists the plugin at the
repo root. Install it straight from GitHub:

```
/plugin marketplace add shantih3112/omniroute-claude-plugin
/plugin install omniroute@omniroute-claude-plugin
```

## Configuration

The MCP server URL is hardcoded to `http://localhost:20128/api/mcp/stream`, matching
OmniRoute's own default port and the exact setup its README recommends for Claude Code.

If your OmniRoute instance runs on a different host/port, or you're driving a remote
OmniRoute over `omniroute connect`, edit the `url` in
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) to match, or add an
`Authorization: Bearer <token>` header there if your instance requires scoped-token auth.

## Verifying it works

After enabling the plugin, ask Claude Code to list its available MCP tools -- you should
see OmniRoute's tools (routing, providers, combos, etc.) alongside any others you have
configured.

## Notes

- OmniRoute is a separate, independently maintained project (MIT-licensed,
  `diegosouzapw/OmniRoute`). This plugin is not affiliated with it; it only points Claude
  Code at an OmniRoute instance you already run.
