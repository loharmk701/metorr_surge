"""Train the rush-hour forecasting model.  Usage: python train_model.py"""
import json

from core.forecast import train

if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
