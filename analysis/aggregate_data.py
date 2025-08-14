#!/usr/bin/env python3
"""
Data Aggregation Script
=======================

This script merges game data with eyetracking data by:
1. Reading parsed game data and extracted gaze data
2. Converting game timesteps to real timestamps using 0.25s intervals
3. Aggregating eyetracking metrics for each game timestep
4. Computing non-zero averages for all eye metrics
5. Generating final merged dataset for analysis

Time Conversion:
- Game timestep 0 → Real time = round_start_time + (0 * 0.25)
- Game timestep 1 → Real time = round_start_time + (1 * 0.25)
- Each timestep covers a 0.25 second window
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys 

def aggregate_eye_metrics(eye_data_window):
    """
    Aggregate eyetracking data for a single game timestep window.
    Computes non-zero averages for all eye metrics.
    
    Args:
        eye_data_window: DataFrame with eyetracking data for one timestep
        
    Returns:
        dict: Aggregated eye metrics
    """
    if len(eye_data_window) == 0:
        return get_empty_eye_metrics()
    
    # Define all eye metric columns to aggregate
    eye_columns = [
        'LPCX', 'LPCY', 'LPD', 'LPS', 'LPV',     # Left eye
        'RPCX', 'RPCY', 'RPD', 'RPS', 'RPV',     # Right eye  
        'SACCADE_MAG', 'SACCADE_DIR',             # Saccade
        'BKID', 'BKDUR', 'BKPMIN'                 # Blink
    ]
    
    metrics = {}
    
    # Aggregate each eye metric using non-zero values
    for col in eye_columns:
        if col in eye_data_window.columns:
            # Get non-zero values
            non_zero_values = eye_data_window[col][(eye_data_window[col] != 0) & (eye_data_window[col].notna())]
            
            if len(non_zero_values) > 0:
                metrics[f'avg_{col.lower()}'] = non_zero_values.mean()
                metrics[f'std_{col.lower()}'] = non_zero_values.std()
                metrics[f'count_{col.lower()}'] = len(non_zero_values)
            else:
                metrics[f'avg_{col.lower()}'] = 0
                metrics[f'std_{col.lower()}'] = 0
                metrics[f'count_{col.lower()}'] = 0
    
    # Add window-level statistics
    metrics['total_samples'] = len(eye_data_window)
    metrics['window_start'] = eye_data_window.iloc[0, 0] if len(eye_data_window) > 0 else np.nan  # First timestamp
    metrics['window_end'] = eye_data_window.iloc[-1, 0] if len(eye_data_window) > 0 else np.nan   # Last timestamp
    
    return metrics

def get_empty_eye_metrics():
    """Return empty eye metrics for timesteps with no eyetracking data"""
    eye_columns = [
        'LPCX', 'LPCY', 'LPD', 'LPS', 'LPV',
        'RPCX', 'RPCY', 'RPD', 'RPS', 'RPV', 
        'SACCADE_MAG', 'SACCADE_DIR', 'BKID', 'BKDUR', 'BKPMIN'
    ]
    
    metrics = {}
    for col in eye_columns:
        metrics[f'avg_{col.lower()}'] = np.nan
        metrics[f'std_{col.lower()}'] = np.nan
        metrics[f'count_{col.lower()}'] = 0
    
    metrics.update({
        'total_samples': 0,
        'window_start': np.nan,
        'window_end': np.nan,
    })
    
    return metrics

def get_round_time_mapping(eye_df):
    """
    Extract time mapping for each round from eyetracking data.
    
    Args:
        eye_df: DataFrame with eyetracking data
        
    Returns:
        dict: Round ID to time info mapping
    """
    time_mapping = {}
    
    for round_id in eye_df['Round_ID'].unique():
        if round_id == -999:  # Skip invalid rounds
            continue
            
        round_data = eye_df[eye_df['Round_ID'] == round_id]
        if len(round_data) > 0:
            time_mapping[round_id] = {
                'start_time': round_data['Interval_Start_s'].iloc[0],
                'end_time': round_data['Interval_End_s'].iloc[0], 
                'duration': round_data['Interval_End_s'].iloc[0] - round_data['Interval_Start_s'].iloc[0],
                'min_timestamp': round_data.iloc[:, 0].min(),  # First column is timestamp
                'max_timestamp': round_data.iloc[:, 0].max(),
                'sample_count': len(round_data)
            }
    
    return time_mapping

def analyze_data_compatibility(participant_id=3):
    """Analyze the compatibility between game and eyetracking data"""
    participants_dir = Path("Participants")
    
    # Check if files exist
    game_file = participants_dir / "outputs" / f"parsed_game_data_{participant_id}.csv"
    eye_file = participants_dir / "outputs" / f"extracted_gaze_data_{participant_id}.csv"
    
    print("📊 Data Compatibility Analysis")
    print("=" * 50)
    
    if not game_file.exists():
        print("❌ Game data file not found. Please run parse_game_logs.py first")
        return False
        
    if not eye_file.exists():
        print("❌ Eyetracking data file not found. Please run extract_gaze_data_fixed.py first")
        return False
    
    # Load and analyze data
    try:
        game_df = pd.read_csv(game_file)
        eye_df = pd.read_csv(eye_file)
        
        print(f"✅ Game data: {len(game_df)} rows")
        print(f"✅ Eyetracking data: {len(eye_df)} rows")
        
        # Analyze rounds
        if len(game_df) > 0:
            game_rounds = set(game_df['round_id'].unique())
        else:
            game_rounds = set()
            
        eye_rounds = set(eye_df['Round_ID'].unique()) - {-999}  # Exclude invalid round
        
        print(f"\n📈 Round Analysis:")
        print(f"  Game rounds: {sorted(game_rounds)}")
        print(f"  Eye rounds: {sorted(eye_rounds)}")
        print(f"  Common rounds: {sorted(game_rounds & eye_rounds)}")
        
        if len(game_df) > 0:
            # Show timestep info for each round
            print(f"\n⏱️ Timestep Analysis:")
            for round_id in sorted(game_rounds):
                round_game = game_df[game_df['round_id'] == round_id]
                if round_id in eye_rounds:
                    round_eye = eye_df[eye_df['Round_ID'] == round_id]
                    duration = round_eye['Interval_End_s'].iloc[0] - round_eye['Interval_Start_s'].iloc[0]
                    print(f"  Round {round_id}: {len(round_game)} game steps, {len(round_eye)} eye samples, {duration:.1f}s duration")
                else:
                    print(f"  Round {round_id}: {len(round_game)} game steps, NO eye data")
        
        return len(game_df) > 0 and len(eye_df) > 0
        
    except Exception as e:
        print(f"❌ Error analyzing data: {e}")
        return False

def aggregate_game_eyetracking_data(participant_id=3):
    """
    Main function to aggregate game and eyetracking data.
    
    Returns:
        bool: Success status
    """
    participants_dir = Path("Participants")
    game_file = participants_dir / "outputs" / f"parsed_game_data_{participant_id}.csv"
    eye_file = participants_dir / "outputs" / f"extracted_gaze_data_{participant_id}.csv"
    output_file = participants_dir / "outputs" / f"aggregated_data_{participant_id}.csv"
    
    print(f"🔄 Starting Data Aggregation for Participant {participant_id}...")
    
    # Check data compatibility first
    if not analyze_data_compatibility():
        return False
    
    # Load data
    try:
        game_df = pd.read_csv(game_file)
        eye_df = pd.read_csv(eye_file)
        
        if len(game_df) == 0:
            print("⚠️ Game data is empty. Cannot proceed with aggregation.")
            return False
            
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return False
    
    # participant id
    game_participant_ids = set(game_df['participant_id'].unique())
    eye_participant_ids = set(eye_df['participant_id'].unique())
    
    if game_participant_ids != {participant_id} or eye_participant_ids != {participant_id}:
        print(f"⚠️ Participant ID mismatch detected!")
        print(f"  Expected: {participant_id}")
        print(f"  Game data: {game_participant_ids}")
        print(f"  Eye data: {eye_participant_ids}")
        return False
    
    print(f"✅ Participant ID verified: {participant_id}")

    # Get time mapping from eyetracking data
    time_mapping = get_round_time_mapping(eye_df)
    
    print(f"\n🔗 Time Mapping:")
    for round_id, info in time_mapping.items():
        print(f"  Round {round_id}: {info['start_time']:.1f}-{info['end_time']:.1f}s "
              f"({info['duration']:.1f}s, {info['sample_count']} samples)")
    
    # Constants
    STEP_INTERVAL = 0.25  # seconds per game timestep
    TIME_WINDOW = STEP_INTERVAL / 2  # ±0.125s window around each timestep
    
    print(f"\n⚙️ Aggregation Settings:")
    print(f"  Step interval: {STEP_INTERVAL}s")
    print(f"  Time window: ±{TIME_WINDOW}s")
    
    # Aggregate data
    aggregated_rows = []
    
    for _, game_row in game_df.iterrows():
        round_id = game_row['round_id']
        timestep = game_row['timestep']
        
        # Start with game data
        agg_row = game_row.to_dict()
        
        if round_id in time_mapping:
            # Calculate real timestamp for this game timestep
            round_info = time_mapping[round_id]
            
            # Linear mapping: distribute game timesteps across actual duration
            max_timestep = game_df[game_df['round_id'] == round_id]['timestep'].max()
            time_ratio = timestep / max_timestep if max_timestep > 0 else 0
            real_timestamp = round_info['min_timestamp'] + (time_ratio * round_info['duration'])
            
            # Find eyetracking samples in time window
            eye_mask = (
                (eye_df['Round_ID'] == round_id) &
                (eye_df.iloc[:, 0] >= real_timestamp - TIME_WINDOW) &  # First column is timestamp
                (eye_df.iloc[:, 0] <= real_timestamp + TIME_WINDOW)
            )
            
            matching_eye_data = eye_df[eye_mask]
            
            # Aggregate eye metrics
            eye_metrics = aggregate_eye_metrics(matching_eye_data)
            agg_row.update(eye_metrics)
            
            # Add timing info
            agg_row['real_timestamp'] = real_timestamp
            agg_row['has_eye_data'] = len(matching_eye_data) > 0
            
        else:
            # No eyetracking data for this round
            eye_metrics = get_empty_eye_metrics()
            agg_row.update(eye_metrics)
            agg_row['real_timestamp'] = np.nan
            agg_row['has_eye_data'] = False
        
        aggregated_rows.append(agg_row)
    
    # Create final DataFrame
    aggregated_df = pd.DataFrame(aggregated_rows)
    
    # Save results
    aggregated_df.to_csv(output_file, index=False)
    
    # Generate summary
    print(f"\n📊 Aggregation Results:")
    print(f"  Total rows: {len(aggregated_df)}")
    print(f"  Rows with eye data: {aggregated_df['has_eye_data'].sum()}")
    print(f"  Coverage: {aggregated_df['has_eye_data'].mean():.1%}")
    
    print(f"\n📈 Coverage by Round:")
    for round_id in aggregated_df['round_id'].unique():
        round_data = aggregated_df[aggregated_df['round_id'] == round_id]
        coverage = round_data['has_eye_data'].mean()
        eye_count = round_data['has_eye_data'].sum()
        total_count = len(round_data)
        print(f"  Round {round_id}: {eye_count}/{total_count} ({coverage:.1%})")
    
    # Add mode switching summary
    print(f"\n🔄 Mode Switching Summary:")
    if 'Current_Mode' in aggregated_df.columns and 'Switch_Attempt' in aggregated_df.columns:
        # Overall statistics
        total_switch_attempts = aggregated_df['Switch_Attempt'].sum()
        print(f"  Total switch attempts: {total_switch_attempts}")

        # Mode distribution
        mode_counts = aggregated_df['Current_Mode'].value_counts().sort_index()
        total_valid_modes = aggregated_df['Current_Mode'].notna().sum()
        print(f"  Mode distribution:")
        for mode, count in mode_counts.items():
            if not pd.isna(mode):
                percentage = (count / total_valid_modes) * 100 if total_valid_modes > 0 else 0
                mode_name = "Human-led" if mode == 0 else "AI-led"
                print(f"    Mode {int(mode)} ({mode_name}): {count} timesteps ({percentage:.1f}%)")
    
    print(f"\n💾 Saved aggregated data to: {output_file}")
    print(f"📊 Columns: {len(aggregated_df.columns)}")
    
    # Show column categories
    game_cols = [col for col in aggregated_df.columns if col in game_df.columns]
    eye_cols = [col for col in aggregated_df.columns if col.startswith(('avg_', 'std_', 'count_'))]
    meta_cols = [col for col in aggregated_df.columns if col in ['real_timestamp', 'has_eye_data', 'total_samples', 'window_start', 'window_end']]
    
    print(f"  📱 Game columns: {len(game_cols)}")
    print(f"  👁️ Eye columns: {len(eye_cols)}")  
    print(f"  🔗 Meta columns: {len(meta_cols)}")
    
    return True

if __name__ == "__main__":
    print("🔄 Game-Eyetracking Data Aggregation Tool")
    print("=" * 50)

    # Get participant ID from command line arguments
    if len(sys.argv) > 1:
        try:
            participant_id = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid participant ID. Please provide a number.")
            sys.exit(1)
    
    else:
        participant_id = 3  # Default fallback
        print(f"⚠️ No participant ID provided, using default: {participant_id}")
    
    print(f"🎯 Processing participant: {participant_id}")
    success = aggregate_game_eyetracking_data(participant_id)
    
    if success:
        print("\n✅ Data aggregation completed successfully!")
        print("📄 Output file: Participants/aggregated_data.csv")
    else:
        print("\n❌ Data aggregation failed. Please check the error messages above.")