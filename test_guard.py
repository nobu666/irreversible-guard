"""Self-check: python3 test_guard.py"""
import json
import os
import tempfile

from guard import reason_for

FIND_RESULT = "\n".join([
    '- ref_20: textbox "ポスト本文" (textbox) - compose box',
    '- ref_42: button "ポストする" (type="button") - inside dialog [ref_11]',
    '- ref_753: button "次へ" (button) - next',
])
TREE_RESULT = "\n".join([
    'dialog "Cart" [ref_11]',
    '  button "Place order" [ref_90]',
    '  link "Back to cart" [ref_91]',
    '- button "Delete account" [ref_50]',
    '- link "Learn more" [ref_60] (see [ref_50] for details)',
])


def transcript(*results):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for i, text in enumerate(results):
        f.write(json.dumps({"message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}", "content": [{"type": "text", "text": text}]}
        ]}}, ensure_ascii=False) + "\n")
    f.close()
    return f.name


def click(ref, path, tool="mcp__Claude_Browser__computer"):
    return {"tool_name": tool, "tool_input": {"action": "left_click", "ref": ref}, "transcript_path": path}


def main():
    t = transcript(FIND_RESULT, TREE_RESULT)
    cases = [
        (True, click("ref_42", t)),                    # ポストする
        (True, click("ref_90", t)),                    # Place order
        (False, click("ref_20", t)),                   # textbox named ポスト本文
        (False, click("ref_753", t)),                  # 次へ
        (False, click("ref_91", t)),                   # Back to cart
        (False, click("ref_11", t)),                   # dialog "Cart": cited inside ref_42's line, must not be read as ポストする
        (True, click("ref_50", t)),                    # Delete account, later cited by ref_60's line
        (False, click("ref_60", t)),                   # Learn more
        (False, click("ref_999", t)),                  # unknown ref
        (False, {"tool_name": "mcp__Claude_Browser__computer",
                 "tool_input": {"action": "left_click", "coordinate": [10, 10]}, "transcript_path": t}),
        (True, {"tool_name": "mcp__claude-in-chrome__browser_batch", "transcript_path": t, "tool_input": {"actions": [
            {"name": "computer", "input": {"action": "left_click", "ref": "ref_20"}},
            {"name": "computer", "input": {"action": "left_click", "ref": "ref_42"}},
        ]}}),
        (True, {"tool_name": "mcp__xapi__send_chat_message", "tool_input": {}}),
        (True, {"tool_name": "mcp__xapi__delete_users_bookmark", "tool_input": {}}),
        (True, {"tool_name": "mcp__gh__deleteRepository", "tool_input": {}}),
        (False, {"tool_name": "mcp__mail__senderInfo", "tool_input": {}}),
        (False, {"tool_name": "mcp__xapi__get_users_posts", "tool_input": {}}),
        (False, {"tool_name": "mcp__xapi__create_users_bookmark", "tool_input": {}}),
        (False, {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}),  # Bash is out of scope
    ]
    fails = [(want, c) for want, c in cases if bool(reason_for(c)) != want]
    os.unlink(t)
    for want, c in fails:
        print("NG", "deny expected" if want else "pass expected", json.dumps(c, ensure_ascii=False)[:160])
    print("OK" if not fails else f"{len(fails)} failed")
    raise SystemExit(bool(fails))


if __name__ == "__main__":
    main()
