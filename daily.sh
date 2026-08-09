#/bin/bash
#

source /home/ai/ai_runner/venv/bin/activate

git pull

python3 run_analysis.py --mode daily

cd /home/ai/ai_runner/stock/output

git add .

git commit -m "daily"

git push


