#!/usr/bin/env python3
"""
Parse Game Logs
Extract structured data from JSON game logs for analysis
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path

def parse_game_log(json_file_path):
    """Parse a single game log file"""
    
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    # Parse trajectory data
    traj_data = []
    for entry in data['traj']:
        try:
            # Parse game state string
            state_str = entry['state']
            state_dict = eval(state_str)  # Convert string to dict
            
            # Extract key information
            parsed_entry = {
                'timestep': entry['t'],
                'score': entry['score'],
                'total_score': state_dict.get('total_score', 0),
                'n_orders': len(state_dict.get('orders', [])),
                'n_objects': len(state_dict.get('objects', {})),
                'n_messages': len(entry.get('message', [])),
                'human_action': entry.get('action', [None, None])[0],
                'ai_action': entry.get('action', [None, None])[1],
                'has_assigned_tasks': len(entry.get('assigned_tasks', [])) > 0,
                'n_assigned_tasks': len(entry.get('assigned_tasks', [])),
                'messages': entry.get('message', []),
                'assigned_tasks': entry.get('assigned_tasks', []),
            }
            
            traj_data.append(parsed_entry)
            
        except Exception as e:
            print(f"  ⚠️ Error parsing timestep {entry['t']}: {e}")
            continue
    
    # Parse other event data
    events_data = {
        'urgent_responses': data.get('urgent_response', []),
        'reflections': data.get('reflection', []),
        'text_actions': data.get('text_action', [])
    }
    
    return pd.DataFrame(traj_data), events_data

def add_round_dependent_columns(df):
    """Add round-dependent columns to the DataFrame"""
    
    # Define the round-dependent values
    round_mapping = {
        0: {'can_switch': False, 'Current_Mode': np.nan, 'Switch_Attempt': 0},
        9: {'can_switch': True, 'Current_Mode': 0, 'Switch_Attempt': 0},
        10: {'can_switch': True, 'Current_Mode': 0, 'Switch_Attempt': 0},
        11: {'can_switch': False, 'Current_Mode': 1, 'Switch_Attempt': 0},
        12: {'can_switch': False, 'Current_Mode': 0, 'Switch_Attempt': 0}
    }
    
    # Initialize columns with default values
    df['can_switch'] = None
    df['Current_Mode'] = int
    df['Switch_Attempt'] = 0
    
    # Apply values based on round_id
    for round_id, values in round_mapping.items():
        mask = df['round_id'] == round_id
        if mask.any():  # Only apply if this round exists in the data
            df.loc[mask, 'can_switch'] = values['can_switch']
            df.loc[mask, 'Current_Mode'] = values['Current_Mode']
            df.loc[mask, 'Switch_Attempt'] = values['Switch_Attempt']
    
        # Load mode switch data and apply switching logic
    participants_dir = Path("Participants")
    mode_switch_file = participants_dir / "mode_switch.csv"
    
    if mode_switch_file.exists():
        print(f"  📊 Loading mode switches from: {mode_switch_file}")
        try:
            switches_df = pd.read_csv(mode_switch_file)
            
            # Process each switch
            for _, switch_row in switches_df.iterrows():
                round_id = switch_row['round']
                switch_timestep = switch_row['timestep']
                
                print(f"    🔄 Processing switch in round {round_id} at timestep {switch_timestep}")
                
                # Get all rows for this round
                round_mask = df['round_id'] == round_id
                round_data = df[round_mask].copy().sort_values('timestep')
                
                if round_data.empty:
                    print(f"      ⚠️ No data found for round {round_id}")
                    continue
                
                # Find the exact timestep or closest >= timestep
                round_timesteps = round_data['timestep'].values
                if switch_timestep in round_timesteps:
                    switch_idx = round_data[round_data['timestep'] == switch_timestep].index[0]
                    actual_timestep = switch_timestep
                else:
                    print(f"      ⚠️ No valid timestep found for switch at {switch_timestep}")
                    continue
                
                # Mark the switch attempt
                df.loc[switch_idx, 'Switch_Attempt'] = 1
                
                # Get current mode and can_switch status
                current_mode = df.loc[switch_idx, 'Current_Mode']
                can_switch = df.loc[switch_idx, 'can_switch']
                
                if pd.isna(current_mode):
                    print(f"      ⚠️ Current_Mode is NaN for round {round_id}, timestep {actual_timestep}")
                    continue
                
                # Apply mode switching logic
                if can_switch:
                    # For rounds with can_switch=True (9, 10): mode changes for rest of round
                    new_mode = 1 - current_mode  # Toggle: 0->1, 1->0
                    
                    # Apply to all subsequent timesteps in this round
                    subsequent_mask = (df['round_id'] == round_id) & (df['timestep'] >= actual_timestep)
                    df.loc[subsequent_mask, 'Current_Mode'] = new_mode
                    
                    affected_count = subsequent_mask.sum()
                    print(f"      ✅ can_switch=True: Changed mode from {current_mode} to {new_mode} for {affected_count} timesteps")
                    
                else:
                    # For rounds with can_switch=False (11, 12): switch attempt recorded but mode unchanged
                    print(f"      🚫 can_switch=False: Switch attempt blocked, mode remains {current_mode}")
            
            print(f"  ✅ Applied {len(switches_df)} mode switches")
            
        except Exception as e:
            print(f"  ❌ Error reading mode switches: {e}")
    else:
        print(f"  📝 No mode_switch.csv found - using default initial modes only")

        # Initialize the new columns
    df['n_human_message'] = 0
    df['n_ai_message'] = 0
    
    # Calculate message counts based on Current_Mode
    for idx, row in df.iterrows():
        current_mode = row['Current_Mode']
        n_messages = row['n_messages']
        
        if pd.isna(current_mode):
            # If mode is NaN, don't assign messages to either category
            df.loc[idx, 'n_human_message'] = 0
            df.loc[idx, 'n_ai_message'] = 0
        elif current_mode == 0:
            # Human-led mode: all messages count as human messages
            df.loc[idx, 'n_human_message'] = n_messages
            df.loc[idx, 'n_ai_message'] = 0
        elif current_mode == 1:
            # AI-led mode: all messages count as AI messages
            df.loc[idx, 'n_human_message'] = 0
            df.loc[idx, 'n_ai_message'] = n_messages
    
    # Show summary of message distribution
    total_human_messages = df['n_human_message'].sum()
    total_ai_messages = df['n_ai_message'].sum()
    total_messages = df['n_messages'].sum()
    
    return df

def parse_all_game_logs():
    """Parse all game log files"""
    
    participants_dir = Path("Participants")
    
    # Game log file mapping
    game_files = {
        0: "Jia_7t85xrps_0_1753279791.931166.json",
        9: "Jia_7t85xrps_9_1753279957.6156886.json",
        10: "Jia_7t85xrps_10_1753280128.7063305.json", 
        11: "Jia_7t85xrps_11_1753280299.124626.json",
        12: "Jia_7t85xrps_12_1753280470.9304807.json"
    }
    
    all_game_data = []
    all_events_data = {}
    
    print("🎮 Parsing Game Logs...")
    
    for round_id, filename in game_files.items():
        file_path = participants_dir / filename
        
        if not file_path.exists():
            print(f"  ❌ Round {round_id}: File not found")
            continue
            
        print(f"  📊 Parsing Round {round_id}...")
        
        try:
            game_df, events = parse_game_log(file_path)
            
            # Add round identifier
            game_df['round_id'] = round_id
            
            # Show timestep info for this round
            min_step = game_df['timestep'].min()
            max_step = game_df['timestep'].max()
            total_steps = len(game_df)
            
            all_game_data.append(game_df)
            all_events_data[round_id] = events
            
            print(f"    ✅ Parsed {total_steps} timesteps (range: {min_step}-{max_step})")
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    # Combine all game data
    if all_game_data:
        combined_game_df = pd.concat(all_game_data, ignore_index=True)

        # Add round-dependent columns
        combined_game_df = add_round_dependent_columns(combined_game_df)
        print("  ✅ Added round-dependent columns: can_switch, Current_Mode, Switch_Attempt")
        
        # Save parsed game data
        output_path = participants_dir / "parsed_game_data.csv"
        combined_game_df.to_csv(output_path, index=False)
        print(f"\n💾 Saved parsed game data to: {output_path}")
        print(f"📊 Total {len(combined_game_df)} game timesteps across all rounds")
        
        # Show summary by round
        print(f"\n📈 Summary by Round:")
        summary = combined_game_df.groupby('round_id').agg({
            'timestep': ['count', 'min', 'max'],
            'total_score': 'last',
            'n_messages': 'sum',
            'n_human_message': 'sum',
            'n_ai_message': 'sum'
        }).round(2)
        print(summary)
        
        return combined_game_df, all_events_data
    
    return None, None


if __name__ == "__main__":
    game_df, events = parse_all_game_logs()
    if game_df is not None:
        print(f"\n✅ Game log parsing completed successfully!")
        print(f"📄 Output file: Participants/parsed_game_data.csv")