from coop_marl.agents.agent import Agent

# from coop_marl.agents.qmix import QMIXAgent
# from coop_marl.agents.mappo_trajedi import MAPPOTrajeDiAgent
# from coop_marl.agents.mappo_sp import MAPPOSPAgent
# from coop_marl.agents.pbt import PBTAgent

__all__ = [
    "Agent",
    # 'QMIXAgent',
    # 'MAPPOTrajeDiAgent',
    # 'MAPPOSPAgent',
    # 'PBTAgent',
]

registered_agents = {a: eval(a) for a in __all__}  # dict([(a,eval(a)) for a in __all__])
