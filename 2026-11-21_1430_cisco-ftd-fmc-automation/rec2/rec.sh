export TERM=xterm-256color
# usage: rec.sh NAME   -> logs/rec2/NAME.cast
mkdir -p /root/ftd-automation/logs/rec2
asciinema rec -q --overwrite -i 3 --cols 110 --rows 34 -c "bash /root/ftd-automation/rec2/$1.sh" /root/ftd-automation/logs/rec2/$1.cast
