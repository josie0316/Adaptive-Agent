#!/usr/bin/env python3
"""
Simple CSV Aggregation
======================

Aggregate all aggregated_data_*.csv files with participant_id as first column.
"""

import pandas as pd
import glob
import os
from pathlib import Path

def aggregate_data():
    """Aggregate all aggregated_data_*.csv files."""
    
    # Look for files in current directory and Participants/outputs
    search_paths = [".", "Participants/outputs"]
    files = []
    
    for path in search_paths:
        if os.path.exists(path):
            pattern = os.path.join(path, "aggregated_data_*.csv")
            found_files = glob.glob(pattern)
            files.extend(found_files)
    
    if not files:
        print("❌ No aggregated_data_*.csv files found!")
        print("Searched in: " + ", ".join(search_paths))
        return None
    
    # Sort files numerically
    files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
    
    print(f"📁 Found {len(files)} files:")
    for i, file in enumerate(files, 1):
        print(f"  {i:2d}. {file}")
    
    # Read and combine
    dfs = []
    for file in files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
            print(f"✓ Added {file}: {df.shape}")
        except Exception as e:
            print(f"❌ Error reading {file}: {e}")
            continue
    
    if not dfs:
        print("❌ No files could be read!")
        return None
    
    # Combine all dataframes
    print(f"\n🔗 Combining {len(dfs)} dataframes...")
    combined = pd.concat(dfs, ignore_index=True)
    
    # Reorder columns to put participant_id first
    if 'participant_id' in combined.columns:
        cols = ['participant_id'] + [c for c in combined.columns if c != 'participant_id']
        combined = combined[cols]
        print("✓ Reordered columns with participant_id first")
    else:
        print("⚠️  Warning: participant_id column not found!")
    
    # Save
    output_file = "combined_aggregated_data.csv"
    combined.to_csv(output_file, index=False)
    
    print(f"\n💾 Saved {output_file}")
    print(f"Final shape: {combined.shape}")
    
    if 'participant_id' in combined.columns:
        participant_count = combined['participant_id'].nunique()
        print(f"Participants: {participant_count}")
        
        # Show participant distribution
        print(f"\n👥 Participant distribution:")
        participant_counts = combined['participant_id'].value_counts().sort_index()
        for pid, count in participant_counts.items():
            print(f"  Participant {pid}: {count:,} records")
    
    return combined

if __name__ == "__main__":
    print("🔍 CSV Aggregation Tool")
    print("=" * 30)
    
    result = aggregate_data()
    
    if result is not None:
        print(f"\n🎉 Aggregation completed successfully!")
    else:
        print(f"\n❌ Aggregation failed!")
