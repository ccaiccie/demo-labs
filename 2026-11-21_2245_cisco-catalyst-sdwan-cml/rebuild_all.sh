#!/bin/bash
# full from-zero rebuild, used for the recorded lesson
cd ~/sdwan-demo/project; . ../.venv/bin/activate
export PYTHONUNBUFFERED=1
echo '$ python reset.py'; python reset.py
echo; echo '$ python build.py --list'; python build.py --list
for s in 1 2 3 4 5 6 7 8 9; do echo; echo "\$ python build.py $s"; python build.py $s || { echo "STEP $s FAILED"; exit 1; }; done
echo; echo '$ python verify.py'; python verify.py
