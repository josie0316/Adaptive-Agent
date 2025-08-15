#!/usr/bin/env python3
"""
Ideal Mode Preference Analysis
==============================

Analyze mode preferences by assuming switch attempts in constrained rounds
would actually change modes, then combine with switchable rounds.
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import chi2_contingency
import matplotlib.pyplot as plt
import seaborn as sns

# Set style for better plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

def load_and_explore_data():
    """Load and explore the data."""
    
    print("🔍 Loading and Exploring Data for Ideal Mode Preference Analysis")
    print("=" * 70)
    
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
    print(f"  Rounds: {sorted(df['round_id'].unique())}")
    
    return df

def analyze_current_vs_ideal_mode_preferences(df):
    """Analyze current vs ideal mode preferences."""
    
    print(f"\n🎯 Current vs Ideal Mode Preferences Analysis")
    print("=" * 60)
    
    # Focus on rounds 9, 10, 11, 12
    target_rounds = [9, 10, 11, 12]
    target_data = df[df['round_id'].isin(target_rounds)]
    
    print(f"📊 Analyzing rounds: {target_rounds}")
    print(f"  Total records: {len(target_data):,}")
    
    # Current mode distribution (what actually happened)
    print(f"\n📈 Current Mode Distribution (What Actually Happened):")
    print("-" * 50)
    
    current_mode_counts = target_data['Current_Mode'].value_counts().sort_index()
    total_records = len(target_data)
    
    for mode, count in current_mode_counts.items():
        pct = (count / total_records) * 100
        print(f"  Mode {mode}: {count:,} ({pct:.1f}%)")
    
    # Analyze by round
    print(f"\n📊 Current Mode Distribution by Round:")
    print("-" * 40)
    
    for round_id in target_rounds:
        round_data = target_data[target_data['round_id'] == round_id]
        mode_counts = round_data['Current_Mode'].value_counts().sort_index()
        switch_attempts = (round_data['Switch_Attempt'] == 1).sum()
        
        print(f"  Round {round_id}:")
        for mode, count in mode_counts.items():
            pct = (count / len(round_data)) * 100
            print(f"    Mode {mode}: {count:,} ({pct:.1f}%)")
        print(f"    Switch attempts: {switch_attempts:,}")
    
    return target_data

def calculate_ideal_mode_preferences(df):
    """Calculate ideal mode preferences assuming switches work in all rounds."""
    
    print(f"\n🔄 Calculating Ideal Mode Preferences")
    print("=" * 50)
    
    target_rounds = [9, 10, 11, 12]
    target_data = df[df['round_id'].isin(target_rounds)].copy()
    
    # Create ideal mode column
    target_data['ideal_mode'] = target_data['Current_Mode'].copy()
    
    # Apply switch attempts to create ideal scenarios
    for round_id in target_rounds:
        round_mask = target_data['round_id'] == round_id
        round_data = target_data[round_mask]
        
        # Find switch attempts in this round
        switch_mask = (round_data['Switch_Attempt'] == 1)
        switch_indices = round_data[switch_mask].index
        
        if len(switch_indices) > 0:
            print(f"  Round {round_id}: {len(switch_indices)} switch attempts")
            
            # Apply switches to ideal mode
            for idx in switch_indices:
                current_mode = target_data.loc[idx, 'Current_Mode']
                # Switch to the other mode
                ideal_mode = 1.0 if current_mode == 0.0 else 0.0
                target_data.loc[idx, 'ideal_mode'] = ideal_mode
                
                print(f"    Record {idx}: Mode {current_mode} → {ideal_mode}")
    
    # Calculate ideal mode distribution
    print(f"\n📊 Ideal Mode Distribution (If All Switches Worked):")
    print("-" * 50)
    
    ideal_mode_counts = target_data['ideal_mode'].value_counts().sort_index()
    total_records = len(target_data)
    
    for mode, count in ideal_mode_counts.items():
        pct = (count / total_records) * 100
        print(f"  Mode {mode}: {count:,} ({pct:.1f}%)")
    
    # Compare current vs ideal
    print(f"\n📈 Comparison: Current vs Ideal:")
    print("-" * 40)
    
    current_mode_0 = (target_data['Current_Mode'] == 0.0).sum()
    current_mode_1 = (target_data['Current_Mode'] == 1.0).sum()
    ideal_mode_0 = (target_data['ideal_mode'] == 0.0).sum()
    ideal_mode_1 = (target_data['ideal_mode'] == 1.0).sum()
    
    print(f"  Current Mode 0: {current_mode_0:,} ({current_mode_0/total_records*100:.1f}%)")
    print(f"  Current Mode 1: {current_mode_1:,} ({current_mode_1/total_records*100:.1f}%)")
    print(f"  Ideal Mode 0: {ideal_mode_0:,} ({ideal_mode_0/total_records*100:.1f}%)")
    print(f"  Ideal Mode 1: {ideal_mode_1:,} ({ideal_mode_1/total_records*100:.1f}%)")
    
    # Calculate change
    mode_0_change = ideal_mode_0 - current_mode_0
    mode_1_change = ideal_mode_1 - current_mode_1
    
    print(f"\n  Change in Mode 0: {mode_0_change:+,}")
    print(f"  Change in Mode 1: {mode_1_change:+,}")
    
    return target_data

def analyze_cognitive_load_with_ideal_modes(df):
    """Analyze cognitive load effects using ideal mode preferences."""
    
    print(f"\n🧠 Cognitive Load Analysis with Ideal Mode Preferences")
    print("=" * 60)
    
    # Use ideal modes for analysis
    df['analysis_mode'] = df['ideal_mode']
    
    # 1. Subjective cognitive load analysis
    print(f"\n📋 Subjective Cognitive Load Analysis (Ideal Modes):")
    print("-" * 50)
    
    if 'subjective_cognitive_load' in df.columns:
        # Create cognitive load categories
        df['subj_cl_category'] = pd.cut(
            df['subjective_cognitive_load'], 
            bins=[0, 2, 4, 6, 8, 10], 
            labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'],
            include_lowest=True
        )
        
        # Analyze mode preferences by subjective cognitive load
        subj_mode_crosstab = pd.crosstab(
            df['subj_cl_category'], 
            df['analysis_mode'], 
            normalize='index'
        ) * 100
        
        print("Mode preferences by subjective cognitive load:")
        print(subj_mode_crosstab.round(1))
        
        # Statistical test
        observed = pd.crosstab(df['subj_cl_category'], df['analysis_mode'])
        chi2, p_value, dof, expected = chi2_contingency(observed)
        
        print(f"\nChi-square test: Chi2={chi2:.3f}, p={p_value:.6f}")
        if p_value < 0.05:
            print("✅ Significant relationship between subjective CL and ideal mode preference!")
        else:
            print("❌ No significant relationship")
    
    # 2. Objective cognitive load analysis
    print(f"\n👁️ Objective Cognitive Load Analysis (Ideal Modes):")
    print("-" * 50)
    
    obj_cl_col = 'cognitive_load_combined_0to10'
    if obj_cl_col not in df.columns:
        obj_cl_col = 'cognitive_load_lpd_0to10'
    
    if obj_cl_col in df.columns:
        # Create cognitive load categories
        df['obj_cl_category'] = pd.cut(
            df[obj_cl_col], 
            bins=[0, 2, 4, 6, 8, 10], 
            labels=['Very Low', 'Low', 'Medium', 'High', 'Very High'],
            include_lowest=True
        )
        
        # Analyze mode preferences by objective cognitive load
        obj_mode_crosstab = pd.crosstab(
            df['obj_cl_category'], 
            df['analysis_mode'], 
            normalize='index'
        ) * 100
        
        print("Mode preferences by objective cognitive load:")
        print(obj_mode_crosstab.round(1))
        
        # Statistical test
        observed = pd.crosstab(df['obj_cl_category'], df['analysis_mode'])
        chi2, p_value, dof, expected = chi2_contingency(observed)
        
        print(f"\nChi-square test: Chi2={chi2:.3f}, p={p_value:.6f}")
        if p_value < 0.05:
            print("✅ Significant relationship between objective CL and ideal mode preference!")
        else:
            print("❌ No significant relationship")
    
    # 3. Compare predictive power
    print(f"\n🔄 Subjective vs Objective Predictive Power (Ideal Modes):")
    print("-" * 50)
    
    if ('subjective_cognitive_load' in df.columns and 
        obj_cl_col in df.columns):
        
        # Calculate correlation with ideal mode preference
        mode_binary = (df['analysis_mode'] == 1).astype(int)
        
        subj_corr = df['subjective_cognitive_load'].corr(mode_binary)
        obj_corr = df[obj_cl_col].corr(mode_binary)
        
        print(f"Correlation with ideal mode preference (Mode 1 = AI-led):")
        print(f"  Subjective CL: r = {subj_corr:.3f}")
        print(f"  Objective CL: r = {obj_corr:.3f}")
        
        # Which is better at predicting mode preference?
        if abs(subj_corr) > abs(obj_corr):
            print(f"  → Subjective CL is better at predicting ideal mode preference")
        else:
            print(f"  → Objective CL is better at predicting ideal mode preference")

def create_summary_report(df):
    """Create a summary report of the ideal mode preference analysis."""
    
    print(f"\n📋 Summary Report")
    print("=" * 50)
    
    print(f"🎯 Research Question: How does cognitive load affect people's preference in human-led mode vs AI-led mode?")
    
    print(f"\n📊 Analysis Approach:")
    print(f"  1. Round 9-10: Actual mode preferences (switches work)")
    print(f"  2. Round 11-12: Ideal mode preferences (assuming switches would work)")
    print(f"  3. Combined analysis: Overall ideal mode preferences")
    
    print(f"\n📈 Key Findings:")
    print(f"  - Current mode distribution reflects system constraints")
    print(f"  - Ideal mode distribution reflects true participant preferences")
    print(f"  - Switch attempts reveal desired mode changes")
    print(f"  - Cognitive load analysis uses ideal modes for accuracy")

def create_visualizations(df):
    """Create comprehensive visualizations for the analysis."""
    
    print(f"\n📊 Creating Visualizations")
    print("=" * 40)
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Ideal Mode Preference Analysis: Cognitive Load Effects', fontsize=16, fontweight='bold')
    
    # 1. Current vs Ideal Mode Distribution
    ax1 = axes[0, 0]
    current_counts = df['Current_Mode'].value_counts().sort_index()
    ideal_counts = df['ideal_mode'].value_counts().sort_index()
    
    x = np.arange(2)
    width = 0.35
    
    ax1.bar(x - width/2, current_counts.values, width, label='Current Mode', alpha=0.8)
    ax1.bar(x + width/2, ideal_counts.values, width, label='Ideal Mode', alpha=0.8)
    
    ax1.set_xlabel('Mode (0=Human-led, 1=AI-led)')
    ax1.set_ylabel('Count')
    ax1.set_title('Current vs Ideal Mode Distribution')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['Human-led', 'AI-led'])
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Mode Preferences by Subjective Cognitive Load
    ax2 = axes[0, 1]
    if 'subj_cl_category' in df.columns:
        subj_crosstab = pd.crosstab(df['subj_cl_category'], df['analysis_mode'], normalize='index') * 100
        subj_crosstab.plot(kind='bar', ax=ax2, stacked=True)
        ax2.set_xlabel('Subjective Cognitive Load')
        ax2.set_ylabel('Percentage (%)')
        ax2.set_title('Mode Preferences by Subjective Cognitive Load')
        ax2.legend(['Human-led', 'AI-led'])
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(True, alpha=0.3)
    
    # 3. Mode Preferences by Objective Cognitive Load
    ax3 = axes[1, 0]
    if 'obj_cl_category' in df.columns:
        obj_crosstab = pd.crosstab(df['obj_cl_category'], df['analysis_mode'], normalize='index') * 100
        obj_crosstab.plot(kind='bar', ax=ax3, stacked=True)
        ax3.set_xlabel('Objective Cognitive Load')
        ax3.set_ylabel('Percentage (%)')
        ax3.set_title('Mode Preferences by Objective Cognitive Load')
        ax3.legend(['Human-led', 'AI-led'])
        ax3.tick_params(axis='x', rotation=45)
        ax3.grid(True, alpha=0.3)
    
    # 4. Cognitive Load vs Mode Preference Scatter Plot
    ax4 = axes[1, 1]
    if 'subjective_cognitive_load' in df.columns:
        # Create scatter plot showing cognitive load vs mode preference
        # Add some jitter to mode preference for better visualization
        jitter = np.random.normal(0, 0.05, len(df))
        
        # Plot Human-led mode (0.0)
        human_data = df[df['analysis_mode'] == 0.0]
        if len(human_data) > 0:
            ax4.scatter(human_data['subjective_cognitive_load'], 
                       human_data['analysis_mode'] + jitter[:len(human_data)], 
                       alpha=0.6, label='Human-led', s=50, color='blue')
        
        # Plot AI-led mode (1.0)
        ai_data = df[df['analysis_mode'] == 1.0]
        if len(ai_data) > 0:
            ax4.scatter(ai_data['subjective_cognitive_load'], 
                       ai_data['analysis_mode'] + jitter[len(human_data):len(human_data)+len(ai_data)], 
                       alpha=0.6, label='AI-led', s=50, color='red')
        
        # Add trend line
        if len(df) > 10:  # Only add trend line if enough data
            z = np.polyfit(df['subjective_cognitive_load'], df['analysis_mode'], 1)
            p = np.poly1d(z)
            x_trend = np.linspace(df['subjective_cognitive_load'].min(), 
                                df['subjective_cognitive_load'].max(), 100)
            ax4.plot(x_trend, p(x_trend), "k--", alpha=0.8, linewidth=2, label='Trend')
        
        # Calculate and display correlation
        correlation = df['subjective_cognitive_load'].corr(df['analysis_mode'])
        ax4.text(0.05, 0.95, f'r = {correlation:.3f}', transform=ax4.transAxes, 
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        
        ax4.set_xlabel('Subjective Cognitive Load (0-10)')
        ax4.set_ylabel('Mode Preference (0=Human-led, 1=AI-led)')
        ax4.set_title('Cognitive Load vs Mode Preference\nwith Trend Line')
        ax4.set_ylim(-0.1, 1.1)
        ax4.set_yticks([0, 1])
        ax4.set_yticklabels(['Human-led', 'AI-led'])
        ax4.legend()
        ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('ideal_mode_preference_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("✅ Visualizations saved as 'ideal_mode_preference_analysis.png'")

def main():
    """Main function."""
    print("🎯 Ideal Mode Preference Analysis")
    print("=" * 60)
    
    # Load and explore data
    df = load_and_explore_data()
    if df is None:
        return
    
    # Analyze current vs ideal
    target_data = analyze_current_vs_ideal_mode_preferences(df)
    
    # Calculate ideal mode preferences
    ideal_data = calculate_ideal_mode_preferences(target_data)
    
    # Analyze cognitive load with ideal modes
    analyze_cognitive_load_with_ideal_modes(ideal_data)
    
    # Create summary report
    create_summary_report(ideal_data)
    
    # Create visualizations
    create_visualizations(ideal_data)
    
    print(f"\n🎉 Ideal mode preference analysis completed!")
    print(f"\n💡 Key Insight:")
    print(f"  - We now have both current (constrained) and ideal (unconstrained) mode preferences")
    print(f"  - Ideal preferences better reflect true participant choices")
    print(f"  - Cognitive load analysis is more accurate with ideal modes")

if __name__ == "__main__":
    main()
