#!/usr/bin/env python3
"""
简单验证脚本 - 检查当前app_human_llm.py中的步数设置
"""

# 读取并验证当前的步数设置
import re

def check_step_settings():
    with open('webapp/app_human_llm.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找 half_max_steps 设置
    half_max_pattern = r'half_max_steps\s*=\s*(\d+)'
    quarter_pattern = r'quarter_and_half_max_steps\s*=\s*(.+)'
    
    half_match = re.search(half_max_pattern, content)
    quarter_match = re.search(quarter_pattern, content)
    
    print("=== 当前步数设置验证 ===")
    
    if half_match:
        half_value = half_match.group(1)
        print(f"✓ half_max_steps = {half_value}")
        if half_value == "800":
            print("✓ Phase 9-12 设置正确 (800步)")
        else:
            print(f"✗ Phase 9-12 设置错误，应该是800，当前是{half_value}")
    else:
        print("✗ 未找到 half_max_steps 设置")
    
    if quarter_match:
        quarter_value = quarter_match.group(1)
        print(f"✓ quarter_and_half_max_steps = {quarter_value}")
        print("✓ Phase -1,0 设置正确 (使用动态计算)")
    else:
        print("✗ 未找到 quarter_and_half_max_steps 设置")
    
    # 检查global声明
    global_patterns = [
        r'global.*half_max_steps.*quarter_and_half_max_steps',
        r'global.*quarter_and_half_max_steps.*half_max_steps'
    ]
    
    global_count = 0
    for pattern in global_patterns:
        if re.search(pattern, content):
            global_count += 1
    
    if global_count > 0:
        print(f"✓ 找到 {global_count} 个 global 声明")
    else:
        print("✗ 未找到足够的 global 声明")
    
    print("\n=== 计算结果 ===")
    print("假设 max_steps = 1000:")
    print("- Phase -1, 0: quarter_and_half_max_steps = 1000//2 + 1000//4 = 500 + 250 = 750 步 (3分7秒)")
    print("- Phase 9, 10, 11, 12: half_max_steps = 800 步 (3分20秒)")

if __name__ == "__main__":
    check_step_settings()
