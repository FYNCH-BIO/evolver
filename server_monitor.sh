#!/bin/bash

supervisor_pid=`ps aux | grep supervisord | grep -v "grep" | awk '{print $2}'`

log_location="/var/log/supervisor/"
previous_log_location="/home/pi/evolver/num_log_lines.txt"
previous_log_count=0
if [ -f $previous_log_location ]; then
    typeset -i previous_log_count=$(cat $previous_log_location)
fi
typeset -i current_log_count=$(sudo wc -l $log_location/*.log | grep "total" | awk '{print $1}')

if [ $previous_log_count -eq $current_log_count ]; then
    echo "Restarting supervisord"
    sudo kill -1 $supervisor_pid
fi

echo $current_log_count > $previous_log_location
