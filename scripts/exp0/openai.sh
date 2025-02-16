#!/bin/bash

models=(
    "4o-mini"
    "4o"
    "o3-mini"
)

for model in "${models[@]}"; do
    for seed in {0..19}; do
        echo "Running $model with seed $seed"
        python llm_agent_run_act.py -m "$model" --seed "$seed"
    done
done
