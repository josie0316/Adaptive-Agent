#!/bin/bash
conda install -c conda-forge gcc -y

pip install --upgrade pip
pip install -r requirements.txt

# install rebar
cd coop_marl/utils/rebar
python setup.py develop
cd ../../..

# install overcooked
cd coop_marl/envs/overcooked/
pip install -e .
cd ../../..

# install coop_marl
python setup.py develop

# cp hooks/pre-push .git/hooks/
# chmod +x .git/hooks/pre-push
