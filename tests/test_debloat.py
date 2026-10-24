import json
import shlex

from lgtv.debloat import PROTECTED, load_bloat_list, luna_command, plan_removal


def test_load_bloat_list_strips_comments_and_blanks(tmp_path):
    f = tmp_path / "bloat.txt"
    f.write_text("# header\n\ncom.a   # note\n  com.b\n#com.c\n")
    assert load_bloat_list(f) == ["com.a", "com.b"]


def test_plan_removal_skips_protected_and_missing():
    installed = {"com.a", "com.webos.app.settings"}
    to_remove, skipped = plan_removal(
        installed, ["com.a", "com.a", "com.webos.app.settings", "com.missing"]
    )
    assert to_remove == ["com.a"]
    assert skipped == {
        "com.webos.app.settings": "protected",
        "com.missing": "not installed",
    }


def test_protected_includes_essentials():
    assert {"com.webos.app.home", "com.webos.app.settings", "org.webosbrew.hbchannel"} <= PROTECTED


def test_luna_command_quotes_payload():
    cmd = luna_command("luna://x/remove", {"id": "a'b"})
    parts = shlex.split(cmd)
    assert parts[:4] == ["luna-send", "-n", "1", "-f"]
    assert parts[4] == "luna://x/remove"
    assert json.loads(parts[5]) == {"id": "a'b"}
