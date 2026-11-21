"""Viewer-facing narration: every step explains what it is doing and why."""
import os, sys, textwrap, time
PAUSE = os.environ.get("DEMO_PAUSE") == "1"   # DEMO_PAUSE=1 waits for Enter between steps (for recording)
W = 78
def step(num, title, why):
    print("\n" + "=" * W)
    print(f" STEP {num}: {title}")
    print("=" * W)
    for line in textwrap.wrap(why, W - 2): print("  " + line)
    print("-" * W); sys.stdout.flush()
    if PAUSE: input("  [press Enter to run this step] ")
def info(msg):  print(f"  -> {msg}"); sys.stdout.flush()
def ok(msg):    print(f"  [OK] {msg}"); sys.stdout.flush()
def warn(msg):  print(f"  [!]  {msg}"); sys.stdout.flush()
