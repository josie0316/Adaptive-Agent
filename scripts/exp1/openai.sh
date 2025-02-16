#!/bin/bash

models=(
    "4o-mini"
    "4o"
    "o3-mini-low"
)

for model in "${models[@]}"; do
    for seed in {0..19}; do
        echo "Running $model with seed $seed"
        echo "##### react #####"
        python llm_agent_run_react_exp_1_2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_single_agent_exp1.yaml
        echo "##### reflexion #####"
        python llm_agent_run_reflexion_exp_1_2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_single_agent_exp1.yaml
        echo "##### dpt w/o tom #####"
        python llm_agent_run_dpt_exp_1_2.py -m "$model" --seed "$seed" --env_config_file config/envs/overcooked_single_agent_exp1.yaml --fsm
    done
done
