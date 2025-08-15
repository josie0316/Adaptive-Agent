#!/usr/bin/env python3
"""
Z-Score to 0-10 Cognitive Load Calculator
==========================================

Calculate objective cognitive load using Z-score standardization
and then map to 0-10 range for easier interpretation.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

def extract_baseline_data():
    """Extract baseline data from extracted_gaze_data_*.csv files."""
    
    print("🔍 Extracting Baseline Data (Round_ID = -999)")
    print("=" * 50)
    
    data_dir = Path("Participants/outputs")
    gaze_files = list(data_dir.glob("extracted_gaze_data_*.csv"))
    
    if not gaze_files:
        print("❌ No extracted_gaze_data_*.csv files found!")
        return None
    
    print(f"📁 Found {len(gaze_files)} gaze data files")
    
    baseline_data = []
    
    for file in gaze_files:
        try:
            participant_id = int(file.stem.split('_')[-1])
            df = pd.read_csv(file)
            
            if 'Round_ID' not in df.columns:
                continue
            
            baseline_mask = df['Round_ID'] == -999
            baseline_records = df[baseline_mask]
            
            if len(baseline_records) > 0:
                # Calculate baseline statistics
                lpd_baseline = baseline_records['LPD'].replace(0, np.nan).mean()
                rpd_baseline = baseline_records['RPD'].replace(0, np.nan).mean()
                lpd_std = baseline_records['LPD'].replace(0, np.nan).std()
                rpd_std = baseline_records['RPD'].replace(0, np.nan).std()
                
                baseline_data.append({
                    'participant_id': participant_id,
                    'lpd_baseline': lpd_baseline,
                    'rpd_baseline': rpd_baseline,
                    'lpd_std': lpd_std,
                    'rpd_std': rpd_std,
                    'baseline_records': len(baseline_records)
                })
                
                print(f"✅ Participant {participant_id}: LPD={lpd_baseline:.2f}±{lpd_std:.2f}, RPD={rpd_baseline:.2f}±{rpd_std:.2f}")
                
        except Exception as e:
            print(f"❌ Error processing {file.name}: {e}")
            continue
    
    if not baseline_data:
        return None
    
    baseline_df = pd.DataFrame(baseline_data)
    print(f"\n📊 Baseline summary:")
    print(f"  Participants: {len(baseline_df)}")
    print(f"  LPD range: {baseline_df['lpd_baseline'].min():.2f} - {baseline_df['lpd_baseline'].max():.2f}")
    print(f"  RPD range: {baseline_df['rpd_baseline'].min():.2f} - {baseline_df['rpd_baseline'].max():.2f}")
    
    return baseline_df

def calculate_zscore_0to10_cognitive_load(combined_data, baseline_data):
    """Calculate cognitive load using Z-score and map to 0-10 range."""
    
    print(f"\n🧠 Calculating Z-Score to 0-10 Cognitive Load")
    print("=" * 50)
    
    data = combined_data.copy()
    
    # Initialize cognitive load columns
    columns = {
        'cognitive_load_lpd_zscore': 'avg_lpd',
        'cognitive_load_rpd_zscore': 'avg_rpd',
        'cognitive_load_lpd_0to10': 'avg_lpd',
        'cognitive_load_rpd_0to10': 'avg_rpd',
        'cognitive_load_combined_0to10': None
    }
    
    for col in columns.keys():
        data[col] = np.nan
    
    # Calculate for each participant
    for _, baseline_row in baseline_data.iterrows():
        participant_id = baseline_row['participant_id']
        participant_mask = data['participant_id'] == participant_id
        
        if participant_mask.sum() == 0:
            continue
        
        # Get participant data
        lpd_data = data.loc[participant_mask, 'avg_lpd'].replace(0, np.nan)
        rpd_data = data.loc[participant_mask, 'avg_rpd'].replace(0, np.nan)
        
        # Calculate Z-score for LPD
        if len(lpd_data.dropna()) > 1:
            lpd_valid = lpd_data.dropna()
            lpd_zscore = stats.zscore(lpd_valid)
            data.loc[lpd_valid.index, 'cognitive_load_lpd_zscore'] = lpd_zscore
            
            # Map Z-score to 0-10 range
            # Z-score -3 to +3 maps to 0 to 10
            lpd_0to10 = ((lpd_zscore + 3) / 6) * 10
            lpd_0to10 = lpd_0to10.clip(0, 10)  # Ensure 0-10 range
            data.loc[lpd_valid.index, 'cognitive_load_lpd_0to10'] = lpd_0to10
        
        # Calculate Z-score for RPD
        if len(rpd_data.dropna()) > 1:
            rpd_valid = rpd_data.dropna()
            rpd_zscore = stats.zscore(rpd_valid)
            data.loc[rpd_valid.index, 'cognitive_load_rpd_zscore'] = rpd_zscore
            
            # Map Z-score to 0-10 range
            rpd_0to10 = ((rpd_zscore + 3) / 6) * 10
            rpd_0to10 = rpd_0to10.clip(0, 10)
            data.loc[rpd_valid.index, 'cognitive_load_rpd_0to10'] = rpd_0to10
        
        # Calculate combined 0-10 cognitive load
        lpd_0to10 = data.loc[participant_mask, 'cognitive_load_lpd_0to10']
        rpd_0to10 = data.loc[participant_mask, 'cognitive_load_rpd_0to10']
        
        both_valid = pd.notna(lpd_0to10) & pd.notna(rpd_0to10)
        if both_valid.sum() > 0:
            combined_0to10 = (lpd_0to10 + rpd_0to10) / 2
            data.loc[participant_mask, 'cognitive_load_combined_0to10'] = combined_0to10
    
    # Summary statistics
    print(f"\n📊 Cognitive Load Summary:")
    print("-" * 40)
    
    # Z-score summary
    for col in ['cognitive_load_lpd_zscore', 'cognitive_load_rpd_zscore']:
        if col in data.columns:
            valid_data = data[col].dropna()
            if len(valid_data) > 0:
                print(f"\n{col}:")
                print(f"  Valid samples: {len(valid_data):,}")
                print(f"  Mean: {valid_data.mean():.3f} (should be ~0)")
                print(f"  Std: {valid_data.std():.3f} (should be ~1)")
                print(f"  Min: {valid_data.min():.3f}")
                print(f"  Max: {valid_data.max():.3f}")
    
    # 0-10 range summary
    for col in ['cognitive_load_lpd_0to10', 'cognitive_load_rpd_0to10', 'cognitive_load_combined_0to10']:
        if col in data.columns:
            valid_data = data[col].dropna()
            if len(valid_data) > 0:
                print(f"\n{col}:")
                print(f"  Valid samples: {len(valid_data):,}")
                print(f"  Mean: {valid_data.mean():.3f}")
                print(f"  Std: {valid_data.std():.3f}")
                print(f"  Min: {valid_data.min():.3f}")
                print(f"  Max: {valid_data.max():.3f}")
                
                # Distribution analysis for 0-10 range
                ranges = [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10)]
                for min_val, max_val in ranges:
                    count = ((valid_data >= min_val) & (valid_data < max_val)).sum()
                    pct = count / len(valid_data) * 100
                    print(f"  Range {min_val}-{max_val}: {count:,} ({pct:.1f}%)")
                
                # Check if distribution is more even
                print(f"  Skewness: {stats.skew(valid_data):.3f}")
                print(f"  Kurtosis: {stats.kurtosis(valid_data):.3f}")
    
    return data

def save_results(data, baseline_data):
    """Save the results."""
    
    print(f"\n💾 Saving Results")
    print("=" * 30)
    
    # Save updated data
    output_file = "combined_aggregated_data_zscore_0to10_cognitive_load.csv"
    data.to_csv(output_file, index=False)
    print(f"✅ Saved: {output_file}")
    
    # Save baseline data
    baseline_file = "baseline_pupil_data_zscore_0to10.csv"
    baseline_data.to_csv(baseline_file, index=False)
    print(f"✅ Saved: {baseline_file}")
    
    print(f"\n📁 File size: {Path(output_file).stat().st_size / 1024 / 1024:.1f} MB")

def compare_all_methods():
    """Compare all cognitive load calculation methods."""
    
    print(f"\n🔄 Method Comparison")
    print("=" * 30)
    
    try:
        # Load previous results for comparison
        files_to_check = [
            "combined_aggregated_data_with_cognitive_load.csv",
            "combined_aggregated_data_zscore_cognitive_load.csv"
        ]
        
        for file_path in files_to_check:
            if Path(file_path).exists():
                prev_data = pd.read_csv(file_path)
                print(f"\n📊 {file_path}:")
                
                # Find cognitive load columns
                cl_cols = [col for col in prev_data.columns if 'cognitive_load' in col.lower()]
                for col in cl_cols:
                    if col in prev_data.columns:
                        cl_data = prev_data[col].dropna()
                        if len(cl_data) > 0:
                            print(f"  {col}:")
                            print(f"    Mean: {cl_data.mean():.3f}")
                            print(f"    Std: {cl_data.std():.3f}")
                            print(f"    Min: {cl_data.min():.3f}")
                            print(f"    Max: {cl_data.max():.3f}")
                            
                            # Show distribution for 0-10 methods
                            if '0to10' in col:
                                ranges = [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10)]
                                for min_val, max_val in ranges:
                                    count = ((cl_data >= min_val) & (cl_data < max_val)).sum()
                                    pct = count / len(cl_data) * 100
                                    print(f"    Range {min_val}-{max_val}: {count:,} ({pct:.1f}%)")
            else:
                print(f"⚠️  File not found: {file_path}")
                
    except Exception as e:
        print(f"⚠️  Could not load previous results for comparison: {e}")

def main():
    """Main function."""
    print("🧠 Z-Score to 0-10 Cognitive Load Calculator")
    print("=" * 50)
    
    # Step 1: Extract baseline data
    baseline_data = extract_baseline_data()
    if baseline_data is None:
        print("❌ Cannot proceed without baseline data!")
        return
    
    # Step 2: Load combined data
    try:
        combined_data = pd.read_csv("combined_aggregated_data.csv")
        print(f"\n✅ Loaded combined data: {combined_data.shape}")
    except Exception as e:
        print(f"❌ Error loading combined data: {e}")
        return
    
    # Step 3: Calculate Z-score to 0-10 cognitive load
    result_data = calculate_zscore_0to10_cognitive_load(combined_data, baseline_data)
    
    # Step 4: Save results
    save_results(result_data, baseline_data)
    
    # Step 5: Compare methods
    compare_all_methods()
    
    print(f"\n🎉 Z-score to 0-10 cognitive load calculation completed!")
    print(f"\n💡 Z-Score to 0-10 Method Advantages:")
    print("  ✅ Z-score provides statistical standardization")
    print("  ✅ 0-10 range is intuitive and easy to interpret")
    print("  ✅ 0 = very low cognitive load (Z-score = -3)")
    print("  ✅ 5 = average cognitive load (Z-score = 0)")
    print("  ✅ 10 = very high cognitive load (Z-score = +3)")
    print("  ✅ Distribution should be more even than baseline-relative method")

if __name__ == "__main__":
    main()
