#!/usr/bin/env python3

import json
import csv
from .logging import Log

def save_json_report(filepath, results_list):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results_list, f, indent=2)
        Log.info(f"JSON report saved to {filepath}")
    except Exception as e:
        Log.error(f"Failed to save JSON report: {e}")

def save_csv_report(filepath, results_list, fieldnames):
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results_list)
        Log.info(f"CSV report saved to {filepath}")
    except Exception as e:
        Log.error(f"Failed to save CSV report: {e}")