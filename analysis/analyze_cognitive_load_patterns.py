#!/usr/bin/env python3
"""
Cognitive Load and Mode Preference Analysis
==========================================

Analyze how cognitive load affects human-led vs AI-led mode preferences.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def load_and_explore_data():
    """Load and explore the cognitive load data."""
    
    print("🔍 Loading and Exploring Cognitive Load Data")
    print("=" * 50)
    
    # Load the data
    try:
        df = pd.read_csv("combined_aggregated_data_zscore_0to10_cognitive_load.csv")
        print(f"✅ Loaded data: {df.shape}")
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None
    
    # Basic info
    print(f"\n📊 Basic Information:")
    print(f"  Total records: {len(df):,}")
    print(f"  Participants: {df['participant_id'].nunique()}")
    print(f"  Rounds: {df['round_id'].nunique()}")
    print(f"  Time range: {df['timestep'].min():.1f} - {df['timestep'].max():.1f}")
    
    # Check cognitive load columns
    cl_cols = [col for col in df.columns if 'cognitive_load' in col.lower()]
    print(f"\n🧠 Cognitive Load Columns: {cl_cols}")
    
    # Check mode-related columns
    mode_cols = [col for col in df.columns if 'mode' in col.lower() or 'switch' in col.lower()]
    print(f"🎮 Mode-related Columns: {mode_cols}")
    
    # Show unique values in key columns
    if 'Current_Mode' in df.columns:
        print(f"\n🎯 Current_Mode values:")
        mode_counts = df['Current_Mode'].value_counts().sort_index()
        for mode, count in mode_counts.items():
            print(f"  Mode {mode}: {count:,} records ({count/len(df)*100:.1f}%)")
    
    if 'Switch_Attempt' in df.columns:
        print(f"\n🔄 Switch_Attempt values:")
        switch_counts = df['Switch_Attempt'].value_counts().sort_index()
        for switch, count in switch_counts.items():
            print(f"  {switch}: {count:,} records ({count/len(df)*100:.1f}%)")
    
    return df

def analyze_cognitive_load_distribution(df):
    """Analyze the distribution of cognitive load."""
    
    print(f"\n📈 Cognitive Load Distribution Analysis")
    print("=" * 50)
    
    # Find cognitive load columns
    cl_cols = [col for col in df.columns if 'cognitive_load' in col.lower() and '0to10' in col]
    
    for col in cl_cols:
        valid_data = df[col].dropna()
        if len(valid_data) > 0:
            print(f"\n{col}:")
            print(f"  Valid samples: {len(valid_data):,}")
            print(f"  Mean: {valid_data.mean():.3f}")
            print(f"  Median: {valid_data.median():.3f}")
            print(f"  Std: {valid_data.std():.3f}")
            print(f"  Min: {valid_data.min():.3f}")
            print(f"  Max: {valid_data.max():.3f}")
            
            # Distribution by ranges
            ranges = [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10)]
            for min_val, max_val in ranges:
                count = ((valid_data >= min_val) & (valid_data < max_val)).sum()
                pct = count / len(valid_data) * 100
                print(f"  Range {min_val}-{max_val}: {count:,} ({pct:.1f}%)")

def analyze_mode_preferences_by_cognitive_load(df):
    """Analyze how cognitive load affects mode preferences."""
    
    print(f"\n🎮 Mode Preferences by Cognitive Load")
    print("=" * 50)
    
    if 'Current_Mode' not in df.columns:
        print("❌ Current_Mode column not found!")
        return
    
    # Use combined cognitive load if available
    cl_col = 'cognitive_load_combined_0to10'
    if cl_col not in df.columns:
        cl_col = 'cognitive_load_lpd_0to10'  # fallback
    
    if cl_col not in df.columns:
        print(f"❌ Cognitive load column not found!")
        return
    
    # Create cognitive load categories
    df['cl_category'] = pd.cut(df[cl_col], 
                              bins=[0, 2, 4, 6, 8, 10], 
                              labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'],
                              include_lowest=True)
    
    # Analyze mode preferences by cognitive load category
    print(f"\n📊 Mode Preferences by Cognitive Load Category:")
    mode_cl_crosstab = pd.crosstab(df['cl_category'], df['Current_Mode'], normalize='index') * 100
    
    print(mode_cl_crosstab.round(1))
    
    # Statistical test (chi-square)
    from scipy.stats import chi2_contingency
    observed = pd.crosstab(df['cl_category'], df['Current_Mode'])
    chi2, p_value, dof, expected = chi2_contingency(observed)
    
    print(f"\n🔬 Chi-square test:")
    print(f"  Chi2: {chi2:.3f}")
    print(f"  p-value: {p_value:.6f}")
    print(f"  Degrees of freedom: {dof}")
    
    if p_value < 0.05:
        print(f"  ✅ Significant relationship between cognitive load and mode preference!")
    else:
        print(f"  ❌ No significant relationship found")
    
    return mode_cl_crosstab

def analyze_switching_behavior(df):
    """Analyze switching behavior in relation to cognitive load."""
    
    print(f"\n🔄 Switching Behavior Analysis")
    print("=" * 50)
    
    if 'Switch_Attempt' not in df.columns:
        print("❌ Switch_Attempt column not found!")
        return
    
    # Use combined cognitive load if available
    cl_col = 'cognitive_load_combined_0to10'
    if cl_col not in df.columns:
        cl_col = 'cognitive_load_lpd_0to10'
    
    if cl_col not in df.columns:
        print(f"❌ Cognitive load column not found!")
        return
    
    # Create cognitive load categories
    df['cl_category'] = pd.cut(df[cl_col], 
                              bins=[0, 2, 4, 6, 8, 10], 
                              labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'],
                              include_lowest=True)
    
    # Analyze switching by cognitive load
    print(f"\n📊 Switching Attempts by Cognitive Load:")
    switch_cl_crosstab = pd.crosstab(df['cl_category'], df['Switch_Attempt'], normalize='index') * 100
    
    print(switch_cl_crosstab.round(1))
    
    # Calculate switching rate by cognitive load
    print(f"\n📈 Switching Rate by Cognitive Load:")
    for category in df['cl_category'].unique():
        if pd.notna(category):
            category_data = df[df['cl_category'] == category]
            total_records = len(category_data)
            switch_records = (category_data['Switch_Attempt'] == 1).sum()
            switch_rate = switch_records / total_records * 100
            print(f"  {category}: {switch_rate:.1f}% ({switch_records:,}/{total_records:,})")

def analyze_subjective_vs_objective(df):
    """Compare subjective and objective cognitive load."""
    
    print(f"\n🧠 Subjective vs Objective Cognitive Load")
    print("=" * 50)
    
    if 'subjective_cognitive_load' not in df.columns:
        print("❌ subjective_cognitive_load column not found!")
        return
    
    # Use combined objective cognitive load
    obj_cl_col = 'cognitive_load_combined_0to10'
    if obj_cl_col not in df.columns:
        obj_cl_col = 'cognitive_load_lpd_0to10'
    
    if obj_cl_col not in df.columns:
        print(f"❌ Objective cognitive load column not found!")
        return
    
    # Remove missing values
    valid_data = df[['participant_id', 'subjective_cognitive_load', obj_cl_col]].dropna()
    
    if len(valid_data) > 0:
        print(f"📊 Correlation Analysis:")
        print(f"  Valid samples: {len(valid_data):,}")
        
        # Calculate correlation
        correlation = valid_data['subjective_cognitive_load'].corr(valid_data[obj_cl_col])
        print(f"  Pearson correlation: {correlation:.3f}")
        
        # Show summary statistics
        print(f"\n📈 Summary Statistics:")
        print(f"  Subjective CL: Mean={valid_data['subjective_cognitive_load'].mean():.2f}, Std={valid_data['subjective_cognitive_load'].std():.2f}")
        print(f"  Objective CL: Mean={valid_data[obj_cl_col].mean():.2f}, Std={valid_data[obj_cl_col].std():.2f}")
        
        # Show correlation by participant
        print(f"\n👥 Correlation by Participant:")
        participant_correlations = []
        for pid in valid_data['participant_id'].unique():
            p_data = valid_data[valid_data['participant_id'] == pid]
            if len(p_data) > 10:  # Need enough data
                corr = p_data['subjective_cognitive_load'].corr(p_data[obj_cl_col])
                participant_correlations.append((pid, corr, len(p_data)))
        
        # Sort by correlation strength
        participant_correlations.sort(key=lambda x: abs(x[1]), reverse=True)
        
        for pid, corr, n in participant_correlations[:10]:
            print(f"  Participant {pid}: r={corr:.3f} (n={n})")

def create_summary_report(df):
    """Create a summary report of the analysis."""
    
    print(f"\n📋 Summary Report")
    print("=" * 50)
    
    print(f"🎯 Research Question: How does cognitive load affect people's preference in human-led mode vs AI-led mode?")
    
    print(f"\n📊 Data Overview:")
    print(f"  Total observations: {len(df):,}")
    print(f"  Participants: {df['participant_id'].nunique()}")
    print(f"  Rounds: {df['round_id'].nunique()}")
    
    print(f"\n🧠 Cognitive Load Data:")
    cl_cols = [col for col in df.columns if 'cognitive_load' in col.lower()]
    for col in cl_cols:
        valid_data = df[col].dropna()
        if len(valid_data) > 0:
            print(f"  {col}: {len(valid_data):,} valid samples")
    
    print(f"\n🎮 Mode Data:")
    if 'Current_Mode' in df.columns:
        mode_counts = df['Current_Mode'].value_counts()
        for mode, count in mode_counts.items():
            print(f"  Mode {mode}: {count:,} records")
    
    print(f"\n🔄 Switching Data:")
    if 'Switch_Attempt' in df.columns:
        switch_counts = df['Switch_Attempt'].value_counts()
        for switch, count in switch_counts.items():
            print(f"  {switch}: {count:,} records")

def main():
    """Main function."""
    print("🧠 Cognitive Load and Mode Preference Analysis")
    print("=" * 60)
    
    # Load and explore data
    df = load_and_explore_data()
    if df is None:
        return
    
    # Perform analyses
    analyze_cognitive_load_distribution(df)
    analyze_mode_preferences_by_cognitive_load(df)
    analyze_switching_behavior(df)
    analyze_subjective_vs_objective(df)
    
    # Create summary report
    create_summary_report(df)
    
    print(f"\n🎉 Analysis completed!")
    print(f"\n💡 Next Steps:")
    print(f"  1. Review the analysis results above")
    print(f"  2. Create visualizations if needed")
    print(f"  3. Run statistical tests for specific hypotheses")
    print(f"  4. Prepare for your RQ1 analysis")

if __name__ == "__main__":
    main()
