#!/bin/bash

models=(
    "4o-mini"
    "4o"
    "o3-mini-low"
)

for model in "${models[@]}"; do
    for ba in {0..2}; do
        for seed in {0..19}; do
            echo "Running $model with seed $seed"
            echo "##### react #####"
            python llm_agent_run_react_exp2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_burger.yaml -ba "$ba"
            echo "##### reflexion #####"
            python llm_agent_run_reflexion_exp2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_burger.yaml -ba "$ba"
            echo "##### dpt #####"
            python llm_agent_run_dpt_exp2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_burger.yaml --infer_human -ba "$ba" --fsm
            echo "##### dpt w/o infer human #####"
            python llm_agent_run_dpt_exp2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_burger.yaml -ba "$ba" --fsm
        done
    done
done
