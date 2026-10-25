"""LG webOS TV debloat tool.

Subcommands:
  apps       List installed apps over the local network (no root needed).
  remove     Uninstall apps over SSH (rooted TV with Homebrew Channel only).
  autostart  Install a boot script that opens the Material launcher (rooted only).

Removal is a dry run unless --yes is given.
"""

import argparse
import asyncio
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

# Apps that keep the TV usable. They are never removed, even if requested.
PROTECTED = {
    "com.webos.app.home",
    "com.webos.app.homeconnect",
    "com.webos.app.livetv",
    "com.webos.app.inputcommon",
    "com.webos.app.hdmi1",
    "com.webos.app.hdmi2",
    "com.webos.app.hdmi3",
    "com.webos.app.hdmi4",
    "com.webos.app.settings",
    "com.palm.app.settings",
    "com.webos.app.softwareupdate",
    "com.webos.app.discovery",  # LG Content Store: needed to reinstall apps
    "org.webosbrew.hbchannel",
    "com.material.launcher",
}

LAUNCHER_ID = "com.material.launcher"
INIT_SCRIPT_PATH = "/var/lib/webosbrew/init.d/50-material-launcher"
KEY_FILE = Path.home() / ".lgtv_client_key"


def load_bloat_list(path):
    """Read app ids from a text file, ignoring blank lines and # comments."""
    ids = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            ids.append(line)
    return ids


def plan_removal(installed, requested, protected=PROTECTED):
    """Split requested ids into (to_remove, skipped) where skipped maps id -> reason."""
    to_remove, skipped = [], {}
    for app_id in dict.fromkeys(requested):
        if app_id in protected:
            skipped[app_id] = "protected"
        elif app_id not in installed:
            skipped[app_id] = "not installed"
        else:
            to_remove.append(app_id)
    return to_remove, skipped


def luna_command(uri, payload):
    """Build a luna-send shell command for running on the TV."""
    return f"luna-send -n 1 -f {shlex.quote(uri)} {shlex.quote(json.dumps(payload))}"


def ssh(host, command, user="root"):
    """Run a command on the TV over SSH and return stdout."""
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", f"{user}@{host}", command],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ssh exited {result.returncode}")
    return result.stdout


def installed_ids_over_ssh(host):
    out = ssh(host, luna_command("luna://com.webos.applicationManager/listApps", {}))
    return {app["id"] for app in json.loads(out).get("apps", [])}


async def list_apps(host):
    from aiowebostv import WebOsClient

    key = KEY_FILE.read_text().strip() if KEY_FILE.exists() else None
    client = WebOsClient(host, key)
    print("Connecting... accept the pairing prompt on the TV if one appears.")
    await client.connect()
    if client.client_key != key:
        KEY_FILE.write_text(client.client_key)
    try:
        apps = await client.get_apps_all()
    finally:
        await client.disconnect()
    for app in sorted(apps, key=lambda a: a["id"]):
        flags = []
        if app["id"] in PROTECTED:
            flags.append("protected")
        if not app.get("removable", True):
            flags.append("system")
        if not app.get("visible", True):
            flags.append("hidden")
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{app['id']:<45} {app.get('title', '')}{suffix}")


def cmd_remove(args):
    requested = list(args.app_ids)
    if args.file:
        requested += load_bloat_list(args.file)
    if not requested:
        sys.exit("Nothing to remove: pass app ids or --file.")

    to_remove, skipped = plan_removal(installed_ids_over_ssh(args.host), requested)
    for app_id, reason in skipped.items():
        print(f"skip    {app_id} ({reason})")
    for app_id in to_remove:
        print(f"remove  {app_id}")
    if not args.yes:
        print("\nDry run. Re-run with --yes to uninstall.")
        return

    for app_id in to_remove:
        cmd = luna_command("luna://com.webos.appInstallService/remove", {"id": app_id})
        try:
            ssh(args.host, cmd)
            print(f"removed {app_id}")
        except RuntimeError as err:
            # Apps baked into firmware live on a read-only partition and will refuse.
            print(f"failed  {app_id}: {err}")


def cmd_autostart(args):
    launch = luna_command(
        "luna://com.webos.service.applicationmanager/launch", {"id": LAUNCHER_ID}
    )
    script = f"#!/bin/sh\nsleep 15\n{launch}\n"
    if args.disable:
        ssh(args.host, f"rm -f {INIT_SCRIPT_PATH}")
        print("Autostart disabled.")
        return
    ssh(
        args.host,
        f"mkdir -p {Path(INIT_SCRIPT_PATH).parent} && "
        f"printf %s {shlex.quote(script)} > {INIT_SCRIPT_PATH} && "
        f"chmod +x {INIT_SCRIPT_PATH}",
    )
    print(f"Launcher will open on boot ({INIT_SCRIPT_PATH}).")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_host = os.environ.get("LGTV_HOST")
    parser.add_argument(
        "--host",
        default=default_host,
        required=default_host is None,
        help="TV IP address (default: $LGTV_HOST)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("apps", help="list installed apps")

    rm = sub.add_parser("remove", help="uninstall apps (rooted TV)")
    rm.add_argument("app_ids", nargs="*")
    rm.add_argument("--file", help="text file of app ids, e.g. bloat.txt")
    rm.add_argument("--yes", action="store_true", help="actually uninstall")

    auto = sub.add_parser("autostart", help="open the launcher on boot (rooted TV)")
    auto.add_argument("--disable", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "apps":
        asyncio.run(list_apps(args.host))
    elif args.command == "remove":
        cmd_remove(args)
    else:
        cmd_autostart(args)


if __name__ == "__main__":
    main()
