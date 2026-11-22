#!/usr/bin/env python3
"""Tear the lab down so you can build it again from zero.

    python reset.py          # stop, wipe and delete the CML lab + local state
    python reset.py --keep   # only stop the lab (keeps all disks, fast restart)

Only the lab named in lab.yaml is touched. Other CML labs are left alone.
"""
from __future__ import annotations

import shutil
import sys

from sdwanlab import config
from build import TITLE, cml, log


def main(keep: bool):
    c = cml()
    lab = c.find_lab(TITLE)
    if not lab:
        log(f"No lab called '{TITLE}' - nothing to do")
    else:
        log(f"Stopping '{TITLE}' ...")
        c.stop_lab(lab)
        if keep:
            log("Stopped. Run 'python build.py 2' later to start it again.")
            return
        c.wipe_lab(lab)
        c.delete_lab(lab)
        log("Lab wiped and deleted")
    if config.STATE.exists():
        shutil.rmtree(config.STATE)
        log("Local state (CA, bootstrap files, IDs) removed")


if __name__ == "__main__":
    main("--keep" in sys.argv)
