"""CM Diagnose — a console tool that times every stage of a member click.

Run it on a fast computer and on the slow computer, then compare the two
reports. Each section isolates one thing that can differ between machines:
network latency to the database file, ODBC connect cost, query time,
connection-cache invalidation (mtime churn), DAO/photo access, and Qt
widget construction speed.

Build: .venv\\Scripts\\pyinstaller Diagnose.spec  ->  dist\\CM Diagnose.exe
Usage: "CM Diagnose.exe"            uses the db path from the app's settings
       "CM Diagnose.exe" --db PATH  test a specific database file
       "CM Diagnose.exe" --no-gui   skip the Qt widget-construction phase
"""
import argparse
import ctypes
import os
import platform
import random
import re
import socket
import subprocess
import sys
import time
from datetime import datetime

# ── report accumulation ──────────────────────────────────────────────
_LINES = []


def say(text: str = ""):
    for line in str(text).splitlines() or [""]:
        _LINES.append(line)
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode(), flush=True)


def header(title: str):
    say()
    say("=" * 64)
    say(title)
    say("=" * 64)


def fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000:8.1f} ms"


class timed:
    """with timed() as t: ...; t.ms holds the elapsed milliseconds."""
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self.t0) * 1000
        return False


def section(title):
    """Decorator: run a section, never let its failure kill the report."""
    def wrap(fn):
        def run(*args, **kwargs):
            header(title)
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                say(f"  !! section failed: {exc!r}")
                return None
        return run
    return wrap


# ── settings (same resolution as the real app) ───────────────────────
def settings_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("APPDATA") or os.path.dirname(sys.executable),
            "BSCA-Members")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "bsca_members_settings.json")


def load_app_settings() -> dict:
    import json
    path = settings_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── sections ─────────────────────────────────────────────────────────
@section("1. SYSTEM")
def sec_system():
    say(f"  Computer name : {socket.gethostname()}")
    say(f"  User          : {os.environ.get('USERNAME', '?')}")
    say(f"  Windows       : {platform.platform()}")
    cpu = platform.processor()
    try:
        import winreg
        with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception:
        pass
    say(f"  CPU           : {cpu}  ({os.cpu_count()} logical cores)")

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    ms = MEMORYSTATUSEX()
    ms.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
        say(f"  RAM           : {ms.ullTotalPhys / 2**30:.1f} GB total, "
            f"{ms.ullAvailPhys / 2**30:.1f} GB free, "
            f"{ms.dwMemoryLoad}% in use")
    say(f"  Python        : {platform.python_version()} "
        f"({'64' if sys.maxsize > 2**32 else '32'}-bit)"
        f"{'  [frozen exe]' if getattr(sys, 'frozen', False) else ''}")
    say(f"  Running from  : {sys.executable}")
    try:
        out = subprocess.run(["powercfg", "/getactivescheme"],
                             capture_output=True, text=True, timeout=10)
        say(f"  Power plan    : {out.stdout.strip().split('(')[-1].rstrip(') ')}")
    except Exception:
        pass


@section("2. DATABASE FILE")
def sec_db_file(db_path: str) -> bool:
    say(f"  Path   : {db_path}")
    if db_path.startswith("\\\\"):
        loc = "network share (UNC)"
    elif "onedrive" in db_path.lower():
        loc = "OneDrive folder (sync client may touch the file!)"
    else:
        drive = os.path.splitdrive(db_path)[0] + "\\"
        kind = ctypes.windll.kernel32.GetDriveTypeW(drive)
        loc = {2: "removable drive", 3: "local fixed disk",
               4: "network mapped drive", 5: "CD", 6: "RAM disk"}.get(
                   kind, f"unknown (type {kind})")
    say(f"  Where  : {loc}")
    if not os.path.exists(db_path):
        say("  !! FILE NOT FOUND - remaining sections will be skipped.")
        return False
    size = os.path.getsize(db_path)
    say(f"  Size   : {size / 2**20:.1f} MB")

    lock = os.path.splitext(db_path)[0] + ".laccdb"
    if os.path.exists(lock):
        say(f"  Lock   : {os.path.basename(lock)} exists "
            "(other computers currently have the DB open)")
    else:
        say("  Lock   : no .laccdb (nobody else connected right now)")

    # stat latency: the app stats the file on EVERY member click
    times = []
    for _ in range(20):
        with timed() as t:
            os.stat(db_path)
        times.append(t.ms)
    say(f"  os.stat x20     : avg {sum(times)/len(times):6.2f} ms, "
        f"max {max(times):6.2f} ms   (paid on every click)")

    # mtime stability: if this changes while nobody edits, the app drops and
    # reopens its ODBC connection on every click (~135 ms+ each time)
    say("  Watching file mtime for 5 seconds...")
    first = os.stat(db_path).st_mtime_ns
    changes = 0
    for _ in range(10):
        time.sleep(0.5)
        now = os.stat(db_path).st_mtime_ns
        if now != first:
            changes += 1
            first = now
    if changes:
        say(f"  !! mtime changed {changes}x in 5s - every change forces a "
            "full ODBC reconnect on the next click")
    else:
        say("  mtime stable - connection cache can be reused between clicks")
    return True


@section("3. FILE READ SPEED (network / disk / antivirus)")
def sec_read_speed(db_path: str):
    size = os.path.getsize(db_path)

    # sequential: how fast bulk pages come off the share
    cap = min(size, 32 * 2**20)
    with open(db_path, "rb") as f:
        with timed() as t:
            remaining = cap
            while remaining > 0:
                chunk = f.read(min(2**20, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
    mbps = (cap / 2**20) / (t.ms / 1000) if t.ms > 0 else 0
    say(f"  Sequential read : {cap / 2**20:.0f} MB in {t.ms:7.0f} ms  "
        f"= {mbps:6.1f} MB/s")

    # random 4 KB reads: approximates ACE page fetches; dominated by
    # round-trip latency when the file is on a share
    rng = random.Random(42)
    lat = []
    with open(db_path, "rb") as f:
        for _ in range(50):
            off = rng.randrange(0, max(1, size - 4096))
            with timed() as t:
                f.seek(off)
                f.read(4096)
            lat.append(t.ms)
    lat.sort()
    say(f"  Random 4KB x50  : avg {sum(lat)/len(lat):6.2f} ms, "
        f"median {lat[25]:6.2f} ms, max {lat[-1]:6.2f} ms")
    say("  (avg > 2 ms usually means network latency or antivirus scanning)")


@section("4. ODBC DRIVER + CONNECT")
def sec_odbc(db_path: str):
    import pyodbc
    access = [d for d in pyodbc.drivers() if "Access" in d]
    say(f"  Access ODBC drivers installed: {access or 'NONE !!'}")

    for i in range(3):
        with timed() as t:
            conn = pyodbc.connect(
                r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
                f"DBQ={db_path};", autocommit=True)
        with timed() as t2:
            conn.close()
        say(f"  Cold connect #{i + 1} : {fmt_ms(t.ms / 1000)}   "
            f"(close {t2.ms:.0f} ms)")
    say("  (a fast machine connects in ~100-200 ms; this cost is paid on "
        "every click whenever the mtime cache misses)")


@section("5. SIMULATED MEMBER CLICKS (the app's real code path)")
def sec_clicks(db_path: str, n_members: int):
    import pyodbc
    from db import members as dbm

    # count reconnects exactly as the app would trigger them
    reconnects = {"n": 0}
    orig_connect = pyodbc.connect

    def counting_connect(*a, **k):
        reconnects["n"] += 1
        return orig_connect(*a, **k)
    pyodbc.connect = counting_connect

    try:
        with timed() as t:
            everyone = dbm.get_all_members(db_path)
        say(f"  Sidebar list load (get_all_members): {fmt_ms(t.ms / 1000)}  "
            f"({len(everyone)} members)")
        if not everyone:
            say("  No members in the database - nothing to click.")
            return

        step = max(1, len(everyone) // n_members)
        sample = everyone[::step][:n_members]

        for label in ("PASS 1 (cold cache)", "PASS 2 (warm cache)"):
            say(f"\n  {label}")
            say(f"  {'member':<28}{'context':>10}{'transport':>10}"
                f"{'reconnect':>11}")
            total = 0.0
            for m in sample:
                before = reconnects["n"]
                with timed() as t1:
                    dbm.get_member_context(m["center_id"], db_path)
                with timed() as t2:
                    dbm.get_transport_authorizations(m["center_id"], db_path)
                total += t1.ms + t2.ms
                name = f"{m['last_name']}, {m['first_name']}"[:26]
                say(f"  {name:<28}{t1.ms:>8.0f} ms{t2.ms:>8.0f} ms"
                    f"{'   YES' if reconnects['n'] > before else '':>11}")
            say(f"  {'-> total DB time for ' + str(len(sample)) + ' clicks':<38}"
                f"{total:>8.0f} ms  (avg {total / len(sample):.0f} ms/click)")
        say(f"\n  ODBC connections opened during this section: "
            f"{reconnects['n']}")
        say("  ('YES' rows / a high count mean the connection cache is being "
            "invalidated - every click pays the full connect cost)")
        return sample
    finally:
        pyodbc.connect = orig_connect


@section("6. DAO / MEMBER PHOTO (loads in background after each click)")
def sec_dao(db_path: str, sample):
    from db import members as dbm
    with timed() as t:
        dbm._dao_database(db_path)
    say(f"  DAO engine + OpenDatabase : {fmt_ms(t.ms / 1000)}  (first time only)")
    cid = sample[0]["center_id"] if sample else None
    if cid is not None:
        with timed() as t:
            data = dbm.get_member_photo(cid, db_path)
        say(f"  Fetch one photo           : {fmt_ms(t.ms / 1000)}  "
            f"({'found, ' + str(len(data) // 1024) + ' KB' if data else 'no photo'})")
    dbm.close_connections()


@section("7. GUI WIDGET BUILD (Qt - CPU/graphics bound)")
def sec_gui(db_path: str, events_path: str, sample):
    from PyQt6.QtWidgets import QApplication
    with timed() as t:
        app = QApplication.instance() or QApplication([])
    say(f"  QApplication startup : {fmt_ms(t.ms / 1000)}  (once per app launch)")

    import gui.member_tabs as mt
    stage = {}
    orig_load, orig_build = (mt.MemberTabsWidget._load_data,
                             mt.MemberTabsWidget._build_ui)

    def timed_load(self):
        with timed() as t:
            orig_load(self)
        stage["load"] = t.ms

    def timed_build(self):
        with timed() as t:
            orig_build(self)
        stage["build"] = t.ms

    mt.MemberTabsWidget._load_data = timed_load
    mt.MemberTabsWidget._build_ui = timed_build
    try:
        say(f"\n  {'member':<28}{'DB load':>10}{'UI build':>10}{'total':>10}")
        say("  (the FIRST row includes one-time init: font/icon caches, "
            "antivirus\n   scanning the Qt DLLs - compare the later rows "
            "between computers)")
        for m in sample[:5]:
            with timed() as t:
                w = mt.MemberTabsWidget(m["center_id"], db_path,
                                        events_path, "", False)
            name = f"{m['last_name']}, {m['first_name']}"[:26]
            say(f"  {name:<28}{stage.get('load', 0):>8.0f} ms"
                f"{stage.get('build', 0):>8.0f} ms{t.ms:>8.0f} ms")
            w.deleteLater()
            app.processEvents()
        say("\n  ('UI build' is pure Qt work on this computer's CPU - if it is "
            "the big number,\n   the bottleneck is the machine, not the "
            "network/database)")
    finally:
        mt.MemberTabsWidget._load_data = orig_load
        mt.MemberTabsWidget._build_ui = orig_build


@section("8. LIVE APP CLICK TEST (drives the running Care Manager)")
def sec_live_clicks(n_clicks: int):
    """Steps through members in the real running app via Windows UI
    Automation and reads the app's own click-to-paint log. Needs a Care
    Manager build from 2026-07-15 or later (the one with the click timer)."""
    # the app's click log (the app always runs frozen -> %APPDATA%)
    base = os.path.join(os.environ.get("APPDATA", ""), "BSCA-Members", "logs")
    if not os.path.isdir(base):
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    log_path = os.path.join(base, f"clicks_{datetime.now():%Y-%m-%d}.txt")

    line_re = re.compile(
        r"center (?P<cid>\S+): click-to-paint (?P<total>\d+) ms "
        r"\(db (?P<db>\d+) \+ ui (?P<ui>\d+) \+ paint (?P<paint>\d+)\)")

    def entries():
        if not os.path.exists(log_path):
            return []
        out = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                m = line_re.search(line)
                if m:
                    out.append({k: (m.group(k) if k == "cid" else int(m.group(k)))
                                for k in ("cid", "total", "db", "ui", "paint")})
        return out

    def wait_new(count_before, timeout=15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            e = entries()
            if len(e) > count_before:
                return e
            time.sleep(0.05)
        return None

    try:
        from pywinauto import Application
    except Exception as exc:
        say(f"  !! UI-automation support failed to load: {exc!r}")
        return
    try:
        # found_index=0: connect refuses an ambiguous match, and users (and
        # test runs) sometimes have more than one Care Manager open.
        # Leading .* also matches older builds titled "Bowery Care Manager".
        app = Application(backend="uia").connect(
            title_re=".*Care Manager.*", timeout=3, found_index=0)
        win = app.top_window()
    except Exception:
        say("  Care Manager is not running - section skipped.")
        say("  To include it: start Care Manager, wait for the member list,")
        say("  then run this diagnostic again (hands off while it clicks).")
        return

    title = win.window_text()
    say(f"  Found window : {title}")
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", title)
    if m and tuple(int(g) for g in m.groups()) < (2026, 7, 15):
        say("  !! This Care Manager build predates 2026-07-15 and has no")
        say("     click timer. Deploy the new exe to the shared folder, then")
        say("     close and relaunch Care Manager from its normal shortcut.")
        return

    win.set_focus()
    member_list = win.child_window(control_type="List", found_index=0)
    rect = member_list.rectangle()
    baseline = len(entries())

    from pywinauto.keyboard import send_keys
    say(f"  Stepping through {n_clicks} members - keep hands off...\n")
    say(f"  {'#':>4}  {'member':<10}{'total':>9}{'db':>8}{'ui':>8}{'paint':>8}")
    member_list.click_input(coords=(rect.width() // 2, 20), absolute=False)
    results = []
    for i in range(n_clicks):
        e = wait_new(baseline, timeout=5 if i == 0 else 15)
        if e is None and i == 0:
            # clicked an already-selected row (no change logged); move once
            send_keys("{DOWN}")
            e = wait_new(baseline)
        if e is None:
            say(f"  {i + 1:>4}  !! nothing logged after 15 s")
            if not os.path.exists(log_path):
                say(f"        Log missing ({log_path}) - old app build?")
            else:
                say("        Log exists but stalled - dialog open / app busy?")
            break
        last = e[-1]
        baseline = len(e)
        results.append(last)
        say(f"  {i + 1:>4}  {last['cid']:<10}{last['total']:>7} ms"
            f"{last['db']:>8}{last['ui']:>8}{last['paint']:>8}")
        if i < n_clicks - 1:
            time.sleep(0.25)
            try:
                # keep the app foregrounded: an occluded window never paints,
                # so the click timer would stall waiting for first paint
                win.set_focus()
            except Exception:
                pass
            send_keys("{DOWN}")

    if results:
        import statistics
        totals = [x["total"] for x in results]
        say(f"\n  clicks measured : {len(results)}")
        say(f"  click-to-paint  : avg {statistics.mean(totals):.0f} ms, "
            f"median {statistics.median(totals):.0f} ms, "
            f"min {min(totals)} ms, max {max(totals)} ms")
        for part, label in (("db", "database (network)"),
                            ("ui", "UI construction   "),
                            ("paint", "layout + paint    ")):
            vals = [x[part] for x in results]
            say(f"    {label} : avg {statistics.mean(vals):6.0f} ms")


# ── main ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Care Manager click diagnostics")
    ap.add_argument("--db", help="database path (default: from app settings)")
    ap.add_argument("--no-gui", action="store_true",
                    help="skip the Qt widget-construction phase")
    ap.add_argument("--clicks", type=int, default=12,
                    help="how many members to click-test (default 12)")
    args = ap.parse_args()

    say("CM DIAGNOSE - Care Manager performance report")
    say(f"Generated : {datetime.now():%Y-%m-%d %H:%M:%S}")

    settings = {}
    try:
        settings = load_app_settings()
        say(f"Settings  : {settings_path()}"
            f"{'' if settings else '  (not found)'}")
    except Exception as exc:
        say(f"Settings  : could not read ({exc!r})")

    db_path = args.db or settings.get("db_path", "")
    events_path = settings.get("events_db_path", "")

    sec_system()

    if not db_path:
        header("DATABASE")
        say("  No database path configured and none passed via --db.")
        say('  Run again as:  "CM Diagnose.exe" --db "\\\\server\\share\\file.accdb"')
    elif sec_db_file(db_path):
        sec_read_speed(db_path)
        sec_odbc(db_path)
        sample = sec_clicks(db_path, args.clicks) or []
        sec_dao(db_path, sample)
        if not args.no_gui and sample:
            sec_gui(db_path, events_path, sample)

    sec_live_clicks(args.clicks)

    header("HOW TO READ THIS")
    say("""  Compare this report against one from a fast computer. Look for:
  * Section 3 random-read avg  > 2 ms      - network latency or antivirus
  * Section 4 cold connect     > 400 ms    - ODBC driver / antivirus / SMB
  * Section 5 'YES' reconnects on pass 2   - DB file mtime keeps changing,
      so every click pays a full reconnect (sync client or another writer)
  * Section 5 warm pass slow but no 'YES'  - query time itself; network
  * Section 7 'UI build' large             - this computer's CPU/graphics
      (check power plan in section 1, and Windows display scaling)
  * Section 8 is the ground truth: real clicks in the real app. Compare
      its db/ui/paint averages between a fast and a slow computer.
  Common fixes: add the .accdb folder and the app to the antivirus
  exclusion list; make sure the computer uses a wired connection or a
  strong 5 GHz signal; set the power plan to Balanced/High performance.""")

    # persist the report somewhere easy to find
    name = f"CM-Diagnose-{socket.gethostname()}-{datetime.now():%Y%m%d-%H%M%S}.txt"
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), name))
    candidates.append(os.path.join(
        os.path.join(os.environ.get("USERPROFILE", "."), "Desktop"), name))
    candidates.append(os.path.join(os.getcwd(), name))
    for path in candidates:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(_LINES) + "\n")
            say("")
            say(f"Report saved to: {path}")
            break
        except OSError:
            continue

    say("")
    input("Done. Press Enter to close...")


if __name__ == "__main__":
    main()
