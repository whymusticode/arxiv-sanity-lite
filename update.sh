#!/bin/bash

# python3 arxiv_daemon.py --num 2000
# python3 compute.py

# nearly 1k papers a day for all of arxiv 

source ~/.venv/bin/activate

cd ~/Documents/arxiv-sanity-lite

timeout 60 python3 arxiv_daemon.py --num 2000
exit_code=$?

if [ $exit_code -eq 124 ]; then
    echo "arxiv_daemon.py timed out after 30 minutes, skipping compute.py"
elif [ $exit_code -eq 0 ]; then
    echo "New papers detected! Running compute.py"
    python3 compute.py
else
    echo "No new papers were added, skipping feature computation"
fi


export FLASK_APP=serve.py
flask run