"""
Soil Sentinel - Main Entry Point.

Runs the automated data collection, preprocessing, and feature engineering pipeline.
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_collection.download_all import run_pipeline


def main():
    print("Executing Soil Sentinel automated data collection and feature engineering pipeline...")
    results = run_pipeline()
    print("\nPipeline execution finished successfully.")
    print(f"- Climate records: {len(results['climate'])}")
    print(f"- Soil depth layers: {len(results['soil'])}")
    print(f"- Combined feature records: {len(results['combined'])}")
    print(f"- Feature table records: {len(results['feature_table'])} records ({len(results['feature_table'].columns)} columns)")
    print(f"- Output path: {results['feature_table_path']}")


if __name__ == "__main__":
    main()

