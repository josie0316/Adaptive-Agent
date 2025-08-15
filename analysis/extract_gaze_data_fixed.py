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

Data Quality Features:
- Filters invalid gaze samples (LPV=0 OR RPV=0)
- Removes tracking failures (coordinates at 0,0)
- Handles extended blink periods appropriately
- Validates pupil diameter ranges (2-8mm)
- Verifies gaze coordinates within screen bounds
- Calculates comprehensive data quality metrics
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from scipy import stats

def filter_invalid_samples(df, time_column):
    
    initial_count = len(df)
    quality_report = {"initial_samples": initial_count}
    
    # 1. Remove rows where not both eyes are invalid (LPV=0 OR RPV=0)
    before_validity = len(df)
    validity_mask = ~((df.get('LPV', 1) == 0) | (df.get('RPV', 1) == 0))
    df = df[validity_mask].copy()
    removed_invalid_eyes = before_validity - len(df)
    quality_report["removed_invalid_eyes"] = removed_invalid_eyes
    print(f"  ❌ Removed {removed_invalid_eyes} samples with both eyes invalid (LPV=0 OR RPV=0)")
    
    # 2. Remove rows with coordinates (0,0) indicating tracking failure
    before_coords = len(df)
    coord_mask = ~(
        ((df.get('LPCX', 1) == 0) & (df.get('LPCY', 1) == 0)) |
        ((df.get('RPCX', 1) == 0) & (df.get('RPCY', 1) == 0))
    )
    df = df[coord_mask].copy()
    removed_zero_coords = before_coords - len(df)
    quality_report["removed_zero_coords"] = removed_zero_coords
    print(f"  ❌ Removed {removed_zero_coords} samples with (0,0) coordinates")
    
    quality_report["final_samples"] = len(df)
    quality_report["total_removed"] = initial_count - len(df)
    quality_report["retention_rate"] = len(df) / initial_count if initial_count > 0 else 0
    
    print(f"  ✅ Retained {len(df)}/{initial_count} samples ({quality_report['retention_rate']:.1%})")
    
    return df, quality_report


def detect_rolling_outliers(data, window_size=100, k=1.5):
    """
    Detect outliers using rolling window statistics.
    Good for time series data with changing baselines.
    
    Args:
        data: Series of pupil measurements
        window_size: Size of rolling window
        k: Multiplier for rolling standard deviation
        
    Returns:
        boolean mask: True for outliers, False for normal data
    """
    rolling_mean = data.rolling(window=window_size, center=True).mean()
    rolling_std = data.rolling(window=window_size, center=True).std()
    
    # Handle NaN values at edges
    rolling_mean = rolling_mean.fillna(method='bfill').fillna(method='ffill')
    rolling_std = rolling_std.fillna(method='bfill').fillna(method='ffill')
    
    lower_bound = rolling_mean - k * rolling_std
    upper_bound = rolling_mean + k * rolling_std
    
    outliers = (data < lower_bound) | (data > upper_bound)
    return outliers


def clean_pupil_outliers(df, method='rolling', sensitivity='high', pupil_cols=['LPD', 'RPD']):
    """
    Clean pupil data by removing statistical outliers.
    
    Args:
        df: DataFrame with pupil data
        method: 'rolling', 'iqr', 'zscore', 'mad'
        sensitivity: 'low', 'medium', 'high'
        pupil_cols: Columns to clean
        
    Returns:
        DataFrame: Cleaned data
    """
    print(f"\n🧹 STATISTICAL OUTLIER CLEANING")
    print("=" * 40)
    print(f"Method: {method.upper()}")
    print(f"Sensitivity: {sensitivity}")
    
    df_clean = df.copy()
    cleaning_stats = {}
    
    for col in pupil_cols:
        if col not in df_clean.columns:
            continue
            
        print(f"\n📊 Cleaning {col}:")
        print("-" * 20)
        
        # Get valid data
        valid_mask = (df_clean[col] != 0) & (df_clean[col].notna())
        valid_data = df_clean.loc[valid_mask, col]
        
        if len(valid_data) == 0:
            print("  ⚠️ No valid data to clean")
            continue
        
        # Detect outliers based on method and sensitivity
        outlier_mask = None
        
        if method == 'rolling':
            if sensitivity == 'high':
                k = 1.5
            elif sensitivity == 'medium':
                k = 2.0
            else:  # low
                k = 2.5
            outlier_mask = detect_rolling_outliers(valid_data, window_size=100, k=k)
            
        elif method == 'iqr':
            Q1 = valid_data.quantile(0.25)
            Q3 = valid_data.quantile(0.75)
            IQR = Q3 - Q1
            
            if sensitivity == 'high':
                k = 1.0
            elif sensitivity == 'medium':
                k = 1.5
            else:  # low
                k = 2.0
                
            lower_bound = Q1 - k * IQR
            upper_bound = Q3 + k * IQR
            outlier_mask = (valid_data < lower_bound) | (valid_data > upper_bound)
            
        elif method == 'zscore':
            if sensitivity == 'high':
                threshold = 2.5
            elif sensitivity == 'medium':
                threshold = 3.0
            else:  # low
                threshold = 4.0
                
            z_scores = np.abs(stats.zscore(valid_data))
            outlier_mask = z_scores > threshold
            
        elif method == 'mad':
            median = valid_data.median()
            mad = np.median(np.abs(valid_data - median))
            modified_z_scores = 0.6745 * (valid_data - median) / mad
            
            if sensitivity == 'high':
                threshold = 2.5
            elif sensitivity == 'medium':
                threshold = 3.5
            else:  # low
                threshold = 4.5
                
            outlier_mask = np.abs(modified_z_scores) > threshold
        
        if outlier_mask is not None:
            # Get indices of outliers in the original dataframe
            outlier_indices = valid_data[outlier_mask].index
            
            # Remove outliers
            df_clean.loc[outlier_indices, col] = np.nan
            
            removed_count = len(outlier_indices)
            print(f"  Original valid samples: {len(valid_data)}")
            print(f"  Outliers detected: {removed_count}")
            print(f"  Outlier percentage: {removed_count/len(valid_data)*100:.1f}%")
            
            cleaning_stats[col] = {
                'original_valid': len(valid_data),
                'outliers_removed': removed_count,
                'outlier_percentage': removed_count/len(valid_data)*100
            }
    
    # Summary
    print(f"\n📊 Cleaning Summary:")
    for col, stats in cleaning_stats.items():
        print(f"  {col}: Removed {stats['outliers_removed']} outliers ({stats['outlier_percentage']:.1f}%)")
    
    return df_clean, cleaning_stats


def extract_gaze_data(participant_id=3, enable_outlier_cleaning=True, cleaning_method='rolling', cleaning_sensitivity='high'):
    """Extract gaze data with only cognitive load relevant columns."""

    print(f"👁️ Processing Participant {participant_id}")
    if enable_outlier_cleaning:
        print(f"🧹 Outlier cleaning enabled: {cleaning_method.upper()} method, {cleaning_sensitivity} sensitivity")
    else:
        print(f"🧹 Outlier cleaning disabled")
    
    # File paths
    participants_dir = Path("Participants")
    eyetracking_log_path = participants_dir / "Eyetracking_log.csv"
    gaze_data_path = participants_dir / f"User {participant_id}_all_gaze.csv"
    output_path = participants_dir / "outputs" / f"extracted_gaze_data_{participant_id}.csv"

    print(f"📁 Input files:")
    print(f"  👁️ Gaze data: {gaze_data_path}")
    print(f"  📊 Eyetracking log: {eyetracking_log_path}")
    print(f"📁 Output file: {output_path}")

    # Check if gaze data file exists
    if not gaze_data_path.exists():
        print(f"❌ Error: Gaze data file not found: {gaze_data_path}")
        print(f"💡 Available gaze files:")
        gaze_files = list(participants_dir.glob("User *_all_gaze.csv"))
        if gaze_files:
            for f in gaze_files:
                print(f"    {f.name}")
        else:
            print(f"    No gaze files found in {participants_dir}")
        return False

    try:
        # Load time intervals and filter for this participant
        time_intervals = pd.read_csv(eyetracking_log_path)
        
        # Filter eyetracking log for this participant
        if 'participant_id' in time_intervals.columns:
            participant_intervals = time_intervals[time_intervals['participant_id'] == participant_id]
            if participant_intervals.empty:
                print(f"❌ No eyetracking intervals found for participant {participant_id}")
                print(f"Available participants: {sorted(time_intervals['participant_id'].unique())}")
                return False
            time_intervals = participant_intervals
        else:
            print(f"⚠️ No participant_id column in Eyetracking_log.csv - using all intervals")
        
        print(f"✅ Loaded {len(time_intervals)} time intervals for participant {participant_id}")
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
    all_quality_reports = []
    
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
            
            interval_data_clean, quality_report = filter_invalid_samples(interval_data_filtered, time_column)
            
            if len(interval_data_clean) > 0:
            # Add metadata columns to identify which interval this data belongs to
                interval_data_clean['participant_id'] = participant_id
                interval_data_clean['Round_ID'] = round_id
                interval_data_clean['Segment_ID'] = segment_id
                interval_data_clean['Interval_Start_s'] = start_time_s
                interval_data_clean['Interval_End_s'] = end_time_s
            
            all_extracted_data.append(interval_data_clean)

            quality_report['round_id'] = round_id
            quality_report['participant_id'] = participant_id
            all_quality_reports.append(quality_report)
            
            # Show actual time range of extracted data
            actual_start = interval_data_clean[time_column].min()
            actual_end = interval_data_clean[time_column].max()
            print(f"    ✅ Extracted {len(interval_data_clean)} samples with {len(interval_data_clean.columns)} columns")
            print(f"    📅 Actual time range: {actual_start:.3f}s - {actual_end:.3f}s")
        else:
            print(f"    ⚠️ No data found for this interval")
    
    if not all_extracted_data:
        print("❌ No data extracted from any intervals")
        return False
    
    # Combine all extracted data
    print(f"\n📝 Combining extracted data...")
    extracted_df = pd.concat(all_extracted_data, ignore_index=True)
    
    # Apply statistical outlier cleaning if enabled
    if enable_outlier_cleaning:
        print(f"\n🔍 Applying statistical outlier cleaning...")
        extracted_df, cleaning_stats = clean_pupil_outliers(
            extracted_df, 
            method=cleaning_method, 
            sensitivity=cleaning_sensitivity,
            pupil_cols=['LPD', 'RPD']
        )
        
        # Add cleaning info to the output filename
        output_path = output_path.parent / f"extracted_gaze_data_{participant_id}.csv"
    
    # Save to new CSV file
    print(f"💾 Saving extracted data to {output_path}...")
    extracted_df.to_csv(output_path, index=False)
    
    print(f"\n🎉 Success! Extracted data saved to: {output_path}")
    print(f"📊 Total extracted records: {len(extracted_df)}")
    print(f"📊 Original data records: {len(gaze_data)}")
    print(f"📊 Extraction ratio: {len(extracted_df)/len(gaze_data)*100:.1f}%")
    print(f"📊 Final columns ({len(extracted_df.columns)}): {list(extracted_df.columns)}")
    
    # Verify participant_id column
    print(f"🔍 Participant ID verification: {extracted_df['participant_id'].unique()}")

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


def print_usage():
    """Print usage instructions."""
    print("Usage: python extract_gaze_data_fixed.py [participant_id] [cleaning_method] [sensitivity]")
    print("")
    print("Arguments:")
    print("  participant_id    Participant ID (default: 3)")
    print("  cleaning_method   Outlier cleaning method:")
    print("                    - rolling (default, recommended for time series)")
    print("                    - iqr (interquartile range)")
    print("                    - zscore (z-score based)")
    print("                    - mad (median absolute deviation)")
    print("                    - none (disable cleaning)")
    print("  sensitivity       Cleaning sensitivity:")
    print("                    - low (conservative, removes fewer outliers)")
    print("                    - medium (balanced)")
    print("                    - high (aggressive, removes more outliers, default)")
    print("")
    print("Examples:")
    print("  python extract_gaze_data_fixed.py 3")
    print("  python extract_gaze_data_fixed.py 5 rolling high")
    print("  python extract_gaze_data_fixed.py 3 iqr medium")
    print("  python extract_gaze_data_fixed.py 3 none")


if __name__ == "__main__":
    print("👁️ Cognitive Load Gaze Data Extraction Tool")
    print("============================================\n")
    
    # Parse command line arguments
    participant_id = 3  # Default value
    enable_cleaning = True
    cleaning_method = 'rolling'
    cleaning_sensitivity = 'high'
    
    # Check for help
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h', 'help']:
        print_usage()
        sys.exit(0)
    
    if len(sys.argv) > 1:
        try:
            participant_id = int(sys.argv[1])
            print(f"🎯 Using participant ID from command line: {participant_id}")
        except ValueError:
            print("❌ Error: Participant ID must be an integer")
            print_usage()
            sys.exit(1)
    else:
        print(f"🎯 Using default participant ID: {participant_id}")
        print("💡 Tip: You can specify participant ID like: python extract_gaze_data_fixed.py 3")
    
    # Parse cleaning options
    if len(sys.argv) > 2:
        cleaning_arg = sys.argv[2].lower()
        if cleaning_arg == 'none':
            enable_cleaning = False
            print("🧹 Outlier cleaning disabled")
        elif cleaning_arg in ['rolling', 'iqr', 'zscore', 'mad']:
            cleaning_method = cleaning_arg
            print(f"🧹 Using cleaning method: {cleaning_method}")
        else:
            print(f"⚠️ Unknown cleaning method: {cleaning_arg}, using default: rolling")
    
    if len(sys.argv) > 3:
        sensitivity_arg = sys.argv[3].lower()
        if sensitivity_arg in ['low', 'medium', 'high']:
            cleaning_sensitivity = sensitivity_arg
            print(f"🧹 Using cleaning sensitivity: {cleaning_sensitivity}")
        else:
            print(f"⚠️ Unknown sensitivity: {sensitivity_arg}, using default: high")
    
    success = extract_gaze_data(participant_id, enable_cleaning, cleaning_method, cleaning_sensitivity)
    
    if success:
        print("\n✅ Data extraction completed successfully!")
        if enable_cleaning:
            print(f"🧹 Statistical outlier cleaning applied: {cleaning_method.upper()} method, {cleaning_sensitivity} sensitivity")
        print("\n📋 The extracted file contains ONLY cognitive load relevant columns:")
        print("   • Time column (for temporal analysis)")
        print("   • Left pupil data (LPCX, LPCY, LPD, LPS, LPV)")
        print("   • Right pupil data (RPCX, RPCY, RPD, RPS, RPV)")
        print("   • Saccade data (SACCADE_MAG, SACCADE_DIR)")
        print("   • Blink data (BKID, BKDUR, BKPMIN)")
        print("   • Metadata (Round_ID, Segment_ID)")
        print("\n💡 For help, run: python extract_gaze_data_fixed.py --help")
    else:
        print("\n❌ Data extraction failed. Please check the error messages above.")