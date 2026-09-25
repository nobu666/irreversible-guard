# irreversible-guard

A Claude Code `PreToolUse` hook that stops irreversible actions before they run: MCP tools like `send_*` or `delete_*`, and browser clicks on buttons labeled "Submit", "Place order", "送信", "投稿", and similar. One Python file, standard library only.

When a rule matches, the hook returns a `deny` decision. Claude sees the reason, tells you what it was about to do, and leaves the final click to you.

## Install

Clone the repo somewhere stable:

```bash
git clone https://github.com/nobu666/irreversible-guard.git ~/repos/irreversible-guard
```

Add the hook to `~/.claude/settings.json` under `hooks.PreToolUse`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/irreversible-guard/guard.py",
            "statusMessage": "checking irreversible actions"
          }
        ]
      }
    ]
  }
}
```

The browser tools are MCP tools too (`mcp__Claude_Browser__*`, `mcp__claude-in-chrome__*`), so this one matcher covers both checks below.

Start a new session so Claude Code picks up the hook.

## Verify

The hook fails open: a wrong path in `settings.json` or an unexpected transcript format means nothing gets stopped, silently. Check it once in a real session. [httpbin's test form](https://httpbin.org/forms/post) is a safe target, since submitting it only echoes the data back. Ask Claude to open it, find the "Submit order" button, and click it. The click should fail with a message like:

```
PreToolUse:mcp__Claude_Browser__computer hook error: 「Submit order」(button) をクリックしようとしています。実行を止めました。…
```

If the form submits instead, the hook is not running.

## What it checks

**1. MCP tool names.** The action part of the tool name (after the last `__`) is matched against a verb list: `send`, `post`, `publish`, `delete`, `remove`, `purge`, `destroy`, `purchase`, `buy`, `pay`, `transfer`, `sign`, `submit`, `merge`. The verb has to be a whole word at the start, so `mcp__xapi__send_chat_message` and `mcp__gh__deleteRepository` are stopped, while `mcp__mail__senderInfo` and `mcp__xapi__get_users_posts` pass.

**2. Browser clicks.** A click through the browser tools only carries an element reference like `ref_42`, not a label. To learn what that ref points at, the hook reads the session transcript and finds the latest tool result that defines it (normally a `read_page` or `find` result):

```
- ref_42: button "ポストする"
  button "Place order" [ref_90]
```

If the element's name contains a word such as submit, send, order, delete, confirm, 送信, 購入, 投稿, or 削除, the click is stopped. Text inputs are exempt, so clicking into a textbox named "ポスト本文" (post body) still works. Clicks inside `browser_batch` are checked one by one.

This covers both the built-in browser of the Claude desktop app (`mcp__Claude_Browser__*`) and Claude in Chrome (`mcp__claude-in-chrome__*`).

## Why `deny` and not `ask`

The first version returned `ask`, hoping for a confirmation prompt. In a session running in auto permission mode, no prompt appeared and the click went through: the hook fired and returned `ask`, but the prompt never reached the user. `deny` stops the call in any permission mode. The cost is that you press the button yourself instead of approving it.

## Limitations

- **Coordinate clicks pass.** A click by `(x, y)` has no element name to check.
- **Key presses pass.** Pressing Enter to submit a form is not a click and is not checked.
- **Unknown refs pass.** If no earlier tool result defines the ref, the hook lets the click through. Stopping on every unknown ref would stop almost every click.
- **Word lists are not exhaustive.** A button labeled "Go" or "OK" that happens to finalize a purchase is not caught. Edit `TOOL_VERBS` and `CLICK_WORDS` in `guard.py` for your own sites and tools.
- **Only MCP tools.** `Bash` and other built-in tools are out of scope; use Claude Code permissions for those.
- **The deny message is in Japanese.** Change `permissionDecisionReason` in `guard.py` if you want another language.
- **The whole transcript is read on each browser click.** Fine for normal sessions; very long ones may add some latency.

## Test

```bash
python3 test_guard.py
```

Prints `OK` when every case passes.

## License

MIT
