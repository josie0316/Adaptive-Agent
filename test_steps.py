#!/usr/bin/env python3

# 简单测试脚本来验证步数设置
import sys
import os
sys.path.append('.')

from coop_marl.utils import create_parser, parse_args

if __name__ == "__main__":
    args, conf, env_conf, _ = parse_args(create_parser())
    
    max_steps = env_conf.get("horizon", 1000)
    print(f"Original max_steps (from config): {max_steps}")
    
    # 模拟webapp中的设置
    half_max_steps = 800  # Set to 800 steps for phases 9, 10, 11, 12
    quarter_and_half_max_steps = max_steps // 2 + max_steps // 4
    env_conf["horizon"] = max(max_steps, half_max_steps, quarter_and_half_max_steps)
    
    print(f"half_max_steps (phases 9-12): {half_max_steps}")
    print(f"quarter_and_half_max_steps (phases -1,0): {quarter_and_half_max_steps}")
    print(f"Updated env_conf horizon: {env_conf['horizon']}")
    
    # 测试不同phase的步数
    print("\nPhase step calculations:")
    for phase in [-1, 0, 9, 10, 11, 12]:
        if phase >= 0:
            _max_steps = half_max_steps
        else:
            _max_steps = quarter_and_half_max_steps
        print(f"Phase {phase}: {_max_steps} steps ({_max_steps * 0.25:.1f} seconds)")
