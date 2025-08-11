#!/usr/bin/env python3
"""
Parse Game Logs
Extract structured data from JSON game logs for analysis
"""

import json
import pandas as pd
import numpy as np
import sys
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

def add_round_dependent_columns(df, participant_id):
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
        print(f"  📊 Loading mode switches for participant {participant_id}...")
        try:
            all_switches_df = pd.read_csv(mode_switch_file)
            switches_df = all_switches_df[all_switches_df['participant_id'] == participant_id]

            print(f"    Found {len(switches_df)} switches for participant {participant_id}")
            
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

def get_participant_name(participant_id):
    """Get participant name from mapping file"""
    participants_dir = Path("Participants")
    mapping_file = participants_dir / "participant_mapping.csv"
    
    if mapping_file.exists():
        try:
            mapping_df = pd.read_csv(mapping_file)
            # Remove any extra spaces from column names
            mapping_df.columns = mapping_df.columns.str.strip()
            
            participant_row = mapping_df[mapping_df['participant_id'] == participant_id]
            if not participant_row.empty:
                return participant_row['participant_name'].iloc[0].strip()
        except Exception as e:
            print(f"  ⚠️ Error reading participant mapping: {e}")
    
    print(f"  ⚠️ No mapping found for participant {participant_id}")
    return None

def find_game_files(participant_name, participants_dir):
    """Dynamically find game log files for a participant"""
    if not participant_name:
        return {}
    
    game_files = {}
    target_rounds = [0, 9, 10, 11, 12]
    
    for round_id in target_rounds:
        # Look for files matching pattern: {name}_*_{round}_*.json
        pattern = f"{participant_name}_*_{round_id}_*.json"
        matching_files = list(participants_dir.glob(pattern))
        
        if matching_files:
            # Use the first matching file
            game_files[round_id] = matching_files[0].name
            print(f"  📁 Found Round {round_id}: {matching_files[0].name}")
        else:
            print(f"  ❌ No file found for Round {round_id} (pattern: {pattern})")
    
    return game_files
def load_questionnaire_data(participant_id):
    """Load questionnaire data for a specific participant"""
    participants_dir = Path("Participants")
    
    # Reuse existing mapping function
    participant_name = get_participant_name(participant_id)
    if not participant_name:
        print(f"  ⚠️ Cannot load questionnaire - no participant name for ID {participant_id}")
        return None
    
    # Find questionnaire JSON file (pattern: {name}_*.json)
    json_files = list(participants_dir.glob(f"{participant_name}_*.json"))
    questionnaire_files = [f for f in json_files if not any(f"_{r}_" in f.name for r in [0, 9, 10, 11, 12])]
    
    if not questionnaire_files:
        print(f"  ⚠️ No questionnaire JSON file found for {participant_name}")
        return None
    
    questionnaire_file = questionnaire_files[0]  # Use first matching file
    print(f"  📋 Loading questionnaire: {questionnaire_file.name}")
    
    try:
        with open(questionnaire_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"  ✅ Loaded questionnaire data for {data.get('name', 'Unknown')}")
        return data
        
    except Exception as e:
        print(f"  ❌ Error loading questionnaire: {e}")
        return None

def extract_team_player_preference(questionnaire_data):
    """Extract team player preference as binary value (single column)"""
    if not questionnaire_data:
        return None, None
    
    team_player_text = questionnaire_data.get('team_player', '')
    
    # Convert to binary: 1 for team_player, 0 for individual_contributor
    if team_player_text == 'team_player':
        return 1, team_player_text
    elif team_player_text == 'individual_contributor':
        return 0, team_player_text
    else:
        print(f"  ⚠️ Unknown team_player value: {team_player_text}")
        return None, team_player_text

def extract_subjective_cognitive_load(questionnaire_data, round_id):
    """Extract subjective cognitive load for a specific round"""
    if not questionnaire_data:
        return None
    
    in_game_data = questionnaire_data.get('in_game', {})
    phase_key = f"phase_{round_id}"
    
    if phase_key in in_game_data:
        phase_data = in_game_data[phase_key]
        cognitive_load = phase_data.get('cognitive_load', '')
        
        try:
            return int(cognitive_load)
        except (ValueError, TypeError):
            print(f"  ⚠️ Invalid cognitive_load for {phase_key}: {cognitive_load}")
            return None
    
    return None

def parse_all_game_logs(participant_id=3):
    """Parse all game log files for a given participant"""
    
    participants_dir = Path("Participants")
    
    # Get participant name from mapping
    participant_name = get_participant_name(participant_id)
    if not participant_name:
        print(f"❌ Cannot find participant name for ID {participant_id}")
        return None, None
    
    print(f"🎮 Parsing Game Logs for Participant {participant_id} ({participant_name})...")
    
    # Dynamically find game files
    questionnaire_data = load_questionnaire_data(participant_id)
    team_player_binary, team_player_text = extract_team_player_preference(questionnaire_data)
    game_files = find_game_files(participant_name, participants_dir)
    
    if not game_files:
        print(f"❌ No game log files found for participant {participant_name}")
        return None, None
    
    all_game_data = []
    all_events_data = {}
    
    print(f"🎮 Parsing Game Logs for Participant {participant_id}...")
    
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
            game_df['participant_id'] = participant_id

            # Add questionnaire data columns
            game_df['team_player'] = team_player_binary 

            # Add subjective cognitive load for this round
            subjective_cognitive_load = extract_subjective_cognitive_load(questionnaire_data, round_id)
            game_df['subjective_cognitive_load'] = subjective_cognitive_load
            
            # Show questionnaire info for this round
            if subjective_cognitive_load is not None:
                print(f"    📋 Subjective cognitive load: {subjective_cognitive_load}")
            else:
                print(f"    📋 No cognitive load data for round {round_id}")
            
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
        combined_game_df = add_round_dependent_columns(combined_game_df, participant_id)
        print("  ✅ Added round-dependent columns: can_switch, Current_Mode, Switch_Attempt")
        
        # Save parsed game data
        output_path = participants_dir / "outputs" / f"parsed_game_data_{participant_id}.csv"
        combined_game_df.to_csv(output_path, index=False)
        print(f"\n💾 Saved parsed game data to: {output_path}")
        print(f"📊 Total {len(combined_game_df)} game timesteps across all rounds")
        
        # Show questionnaire summary
        if questionnaire_data:
            print(f"\n📋 Questionnaire Data Summary:")
            print(f"  Team player: {team_player_text} (binary: {team_player_binary})")
            
            # Show cognitive loads by round
            cognitive_loads = {}
            for round_id in game_files.keys():
                load = extract_subjective_cognitive_load(questionnaire_data, round_id)
                if load is not None:
                    cognitive_loads[round_id] = load
            
            if cognitive_loads:
                print(f"  Subjective cognitive loads: {cognitive_loads}")
                print(f"  Cognitive load range: {min(cognitive_loads.values())}-{max(cognitive_loads.values())}")
            else:
                print(f"  No cognitive load data available")

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

    if len(sys.argv) > 1:
        participant_id = int(sys.argv[1])
        print(f"🎯 Using participant ID from command line: {participant_id}")
    else:
        participant_id = 3  # Default value
        print(f"🎯 Using default participant ID: {participant_id}")

    game_df, events = parse_all_game_logs(participant_id)
    if game_df is not None:
        print(f"\n✅ Game log parsing completed successfully for participant {participant_id}!")
        print(f"📄 Output file: Participants/parsed_game_data_participant_{participant_id}.csv")