#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block irreversible actions.

Two checks:
  1. Tool name: MCP tools whose action verb is irreversible (send_*, delete_*, ...).
  2. Browser clicks: the clicked `ref_N` is looked up in earlier read_page/find
     results in the transcript, and the element's name is matched against a
     word table ("Submit", "投稿", ...).

Prints a `deny` decision when a rule matches; prints nothing otherwise.
"""
import json
import re
import sys

# Verb at the start of the tool's action name (the part after the last "__").
TOOL_VERBS = re.compile(
    r"^(send|post|publish|delete|remove|purge|destroy|purchase|buy|pay|transfer|sign|submit|merge)(_|$|(?=[A-Z]))"
)

# Words in a button/link name that mean "this click cannot be taken back".
CLICK_WORDS = re.compile(
    r"送信|署名|購入|注文|支払|決済|同意|承諾|投稿|ポストする|公開|削除|確定|退会|解約|"
    r"\b(submit|send|sign|buy|purchase|pay|order|checkout|accept|agree|confirm|delete|remove|publish|post|transfer)\b",
    re.IGNORECASE,
)

# Roles where typing happens, not committing ("ポスト本文" textbox must pass).
INPUT_ROLES = {"textbox", "searchbox", "combobox", "textarea", "input"}

BROWSER_TOOL = re.compile(r"__(computer|browser_batch)$")


def clicked_refs(tool_name, tool_input):
    """Refs clicked by a computer call, including actions inside browser_batch."""
    if tool_name.endswith("browser_batch"):
        for a in tool_input.get("actions", []):
            yield from clicked_refs(a.get("name", ""), a.get("input", {}))
    elif tool_name.endswith("computer") and "click" in str(tool_input.get("action", "")):
        # ponytail: coordinate-only clicks carry no element name and pass unchecked.
        if tool_input.get("ref"):
            yield tool_input["ref"]


def result_texts(transcript_path):
    """Text of every tool result in the transcript, oldest first."""
    try:
        f = open(transcript_path, encoding="utf-8")
    except OSError:
        return
    with f:
        for line in f:
            if '"tool_result"' not in line:
                continue
            try:
                content = json.loads(line)["message"]["content"]
            except (ValueError, KeyError, TypeError):
                continue
            for c in content if isinstance(content, list) else []:
                if not isinstance(c, dict) or c.get("type") != "tool_result":
                    continue
                body = c.get("content")
                if isinstance(body, str):
                    yield body
                elif isinstance(body, list):
                    for b in body:
                        if isinstance(b, dict) and b.get("type") == "text":
                            yield b.get("text", "")


def element_of(ref, transcript_path):
    """(role, name) from the latest tool-result line mentioning ref, or None.

    Handles both `ref_42: button "Post"` (find) and `button "Post" [ref_42]` (read_page).
    """
    # ponytail: reads the whole transcript per browser click; tail-read if it gets slow.
    r = re.escape(ref)
    # Only the element's own tag counts; descriptions may cite other refs
    # ("inside dialog [ref_11]", "link ... [ref_60] (see [ref_50])").
    own_find = re.compile(rf"^\s*-?\s*{r}:")                              # - ref_42: button "Post"
    own_tree = re.compile(rf'^\s*-?\s*[A-Za-z][\w-]*\s+"[^\[]*?\[{r}\]')  # - button "Post" [ref_42]
    last = None
    for text in result_texts(transcript_path):
        for line in text.splitlines():
            if own_find.search(line) or own_tree.search(line):
                last = line
    if last is None:
        return None
    m = re.search(r'([A-Za-z]+)\s+"+([^"]*)"', last)
    return (m.group(1).lower(), m.group(2)) if m else ("", last)


def reason_for(payload):
    name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if name.startswith("mcp__") and TOOL_VERBS.search(name.rsplit("__", 1)[-1]):
        return f"{name} は取り消せない操作の可能性があります"

    if BROWSER_TOOL.search(name):
        for ref in clicked_refs(name, tool_input):
            el = element_of(ref, payload.get("transcript_path", ""))
            if el is None:
                continue  # ponytail: unknown ref passes; ask-on-unknown would fire on every click
            role, label = el
            if role not in INPUT_ROLES and CLICK_WORDS.search(label):
                return f"「{label}」({role or '要素'}) をクリックしようとしています"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    reason = reason_for(payload)
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason + "。実行を止めました。ユーザーにチャットで確認し、ユーザー自身に操作してもらってください。",
            }
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
