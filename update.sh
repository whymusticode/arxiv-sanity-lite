
# python3 arxiv_daemon.py --num 2000
# python3 compute.py

# nearly 1k papers a day for all of arxiv 

# source ./.venv/bin/activate

cd ~/Documents/arxiv-sanity-lite

timeout 10 python3 arxiv_daemon.py --num 2000
exit_code=$?

if [ $exit_code -eq 124 ]; then
    echo "arxiv_daemon.py timed out"
elif [ $exit_code -eq 0 ]; then
    echo "New papers detected!"
else
    echo "No new papers were added??"
fi
python3 compute.py


export FLASK_APP=serve.py
flask run