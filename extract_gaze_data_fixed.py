#!/usr/bin/env python3
"""
Cognitive Load Gaze Data Extraction Script
==========================================

This script extracts only the cognitive load relevant columns from gaze data 
based on time intervals from Eyetracking_log.csv.

Columns extracted:
- TIME column (any column starting with 'TIME')
- Left pupil: LPCX, LPCY, LPD, LPS, LPV
- Right pupil: RPCX, RPCY, RPD, RPS, RPV  
- Saccade: SACCADE_MAG, SACCADE_DIR
- Blink: BKID, BKDUR, BKPMIN
- Metadata: Round_ID, Segment_ID, Cognitive_load, Score
"""

import pandas as pd
from pathlib import Path

def extract_gaze_data():
    """Extract gaze data with only cognitive load relevant columns."""
    
    # File paths
    participants_dir = Path("Participants")
    eyetracking_log_path = participants_dir / "Eyetracking_log.csv"
    gaze_data_path = participants_dir / "User 3_all_gaze.csv"
    output_path = participants_dir / "extracted_gaze_data_fixed.csv"

    try:
        # Load time intervals
        time_intervals = pd.read_csv(eyetracking_log_path)
        print(f"✅ Loaded {len(time_intervals)} time intervals")
        print("Time intervals:")
        print(time_intervals.to_string())
    except FileNotFoundError:
        print(f"❌ Error: {eyetracking_log_path} not found")
        return False
    except Exception as e:
        print(f"❌ Error loading time intervals: {e}")
        return False
    
    print(f"\n👁️ Loading gaze data...")
    try:
        # Load gaze data
        gaze_data = pd.read_csv(gaze_data_path)
        print(f"✅ Loaded gaze data with {len(gaze_data)} records")
        
        # Find the correct TIME column - look for any column starting with 'TIME'
        time_column = None
        available_columns = list(gaze_data.columns)
        print(f"Available columns: {available_columns[:10]}...")  # Show first 10 columns
        
        # Look for any column that starts with 'TIME' (including formatted ones)  
        for col in gaze_data.columns:
            if col.upper().startswith('TIME'):
                time_column = col
                print(f"✅ Found TIME column: {col}")
                break
        
        if time_column is None:
            print("❌ No TIME column found!")
            return False
        
        # Define ONLY the columns we want to keep for cognitive load analysis
        required_columns = [
            'LPCX', 'LPCY', 'LPD', 'LPS', 'LPV',  # Left pupil
            'RPCX', 'RPCY', 'RPD', 'RPS', 'RPV',  # Right pupil  
            'SACCADE_MAG', 'SACCADE_DIR',         # Saccade
            'BKID', 'BKDUR', 'BKPMIN'             # Blink
        ]
        
        # Find which columns exist in the data
        columns_to_keep = [time_column]  # Always keep the time column
        missing_columns = []
        
        for req_col in required_columns:
            found = False
            for col in available_columns:
                if col.upper() == req_col.upper():
                    columns_to_keep.append(col)
                    found = True
                    break
            if not found:
                missing_columns.append(req_col)
        
        print(f"\n📋 Column Selection Summary:")
        print(f"✅ Columns to keep ({len(columns_to_keep)}): {columns_to_keep}")
        if missing_columns:
            print(f"⚠️ Missing columns ({len(missing_columns)}): {missing_columns}")
        
        print(f"Using time column: {time_column}")
        print(f"Time range in data: {gaze_data[time_column].min():.3f} - {gaze_data[time_column].max():.3f} seconds")
        
    except FileNotFoundError:
        print(f"❌ Error: {gaze_data_path} not found")
        return False
    except Exception as e:
        print(f"❌ Error loading gaze data: {e}")
        return False
    
    print(f"\n🔍 Extracting data for time intervals...")
    
    # Create an empty list to store all extracted data
    all_extracted_data = []
    
    # Extract data for each time interval
    for i, row in time_intervals.iterrows():
        round_id = row['Round_ID']
        segment_id = row['Segment_ID'] if pd.notna(row['Segment_ID']) else 'Unknown'
        start_time_s = row['Start_Time_s']
        end_time_s = row['End_Time_s']
        
        print(f"  Extracting Round {round_id}, Segment {segment_id}: {start_time_s}s - {end_time_s}s")
        
        # Filter gaze data for this time interval using the correct time column
        mask = (gaze_data[time_column] >= start_time_s) & (gaze_data[time_column] <= end_time_s)
        interval_data = gaze_data[mask].copy()
        
        if len(interval_data) > 0:
            # Keep ONLY the specified columns for cognitive load analysis
            interval_data_filtered = interval_data[columns_to_keep].copy()
            
            # Add metadata columns to identify which interval this data belongs to
            interval_data_filtered['Round_ID'] = round_id
            interval_data_filtered['Segment_ID'] = segment_id
            interval_data_filtered['Interval_Start_s'] = start_time_s
            interval_data_filtered['Interval_End_s'] = end_time_s
            
            # Add other metadata if available
            if 'Cognitive_load' in row and pd.notna(row['Cognitive_load']):
                interval_data_filtered['Cognitive_load'] = row['Cognitive_load']
            if 'Score' in row and pd.notna(row['Score']):
                interval_data_filtered['Score'] = row['Score']
            
            all_extracted_data.append(interval_data_filtered)
            
            # Show actual time range of extracted data
            actual_start = interval_data_filtered[time_column].min()
            actual_end = interval_data_filtered[time_column].max()
            print(f"    ✅ Extracted {len(interval_data_filtered)} samples with {len(interval_data_filtered.columns)} columns")
            print(f"    📅 Actual time range: {actual_start:.3f}s - {actual_end:.3f}s")
        else:
            print(f"    ⚠️ No data found for this interval")
    
    if not all_extracted_data:
        print("❌ No data extracted from any intervals")
        return False
    
    # Combine all extracted data
    print(f"\n📝 Combining extracted data...")
    extracted_df = pd.concat(all_extracted_data, ignore_index=True)
    
    # Save to new CSV file
    print(f"💾 Saving extracted data to {output_path}...")
    extracted_df.to_csv(output_path, index=False)
    
    print(f"\n🎉 Success! Extracted data saved to: {output_path}")
    print(f"📊 Total extracted records: {len(extracted_df)}")
    print(f"📊 Original data records: {len(gaze_data)}")
    print(f"📊 Extraction ratio: {len(extracted_df)/len(gaze_data)*100:.1f}%")
    print(f"📊 Final columns ({len(extracted_df.columns)}): {list(extracted_df.columns)}")
    
    # Show summary of extracted data
    print(f"\n📈 Summary by interval:")
    summary = extracted_df.groupby(['Round_ID', 'Segment_ID']).agg({
        time_column: ['count', 'min', 'max']
    }).round(3)
    print(summary)
    
    # Show data quality summary for cognitive load metrics
    print(f"\n🧠 Cognitive Load Metrics Data Quality:")
    
    # Pupil data quality
    pupil_cols = [col for col in extracted_df.columns if any(p in col.upper() for p in ['LPD', 'RPD', 'LPV', 'RPV'])]
    if pupil_cols:
        print(f"  👁️ Pupil data columns: {pupil_cols}")
        for col in pupil_cols:
            valid_count = extracted_df[col].notna().sum()
            total_count = len(extracted_df)
            print(f"    {col}: {valid_count}/{total_count} ({valid_count/total_count*100:.1f}% valid)")
    
    # Saccade data quality
    saccade_cols = [col for col in extracted_df.columns if 'SACCADE' in col.upper()]
    if saccade_cols:
        print(f"  🔄 Saccade data columns: {saccade_cols}")
        for col in saccade_cols:
            valid_count = extracted_df[col].notna().sum()
            total_count = len(extracted_df)
            print(f"    {col}: {valid_count}/{total_count} ({valid_count/total_count*100:.1f}% valid)")
    
    # Blink data quality
    blink_cols = [col for col in extracted_df.columns if col.upper().startswith('BK')]
    if blink_cols:
        print(f"  👀 Blink data columns: {blink_cols}")
        for col in blink_cols:
            valid_count = extracted_df[col].notna().sum()
            total_count = len(extracted_df)
            print(f"    {col}: {valid_count}/{total_count} ({valid_count/total_count*100:.1f}% valid)")
    
    return True

if __name__ == "__main__":
    print("👁️ Cognitive Load Gaze Data Extraction Tool")
    print("============================================\n")
    
    success = extract_gaze_data()
    
    if success:
        print("\n✅ Data extraction completed successfully!")
        print("Output file: Participants/extracted_gaze_data_fixed.csv")
        print("\n📋 The extracted file contains ONLY cognitive load relevant columns:")
        print("   • Time column (for temporal analysis)")
        print("   • Left pupil data (LPCX, LPCY, LPD, LPS, LPV)")
        print("   • Right pupil data (RPCX, RPCY, RPD, RPS, RPV)")
        print("   • Saccade data (SACCADE_MAG, SACCADE_DIR)")
        print("   • Blink data (BKID, BKDUR, BKPMIN)")
        print("   • Metadata (Round_ID, Segment_ID, Cognitive_load, Score)")
    else:
        print("\n❌ Data extraction failed. Please check the error messages above.")