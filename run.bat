@echo off
REM One-click setup + run. Data/model steps are skipped if outputs already exist.
pip install -r requirements.txt -q
if not exist data\ridership_hourly.csv python data\generate_data.py
if not exist model\rush_model.joblib python train_model.py
start http://localhost:5000
python app.py
