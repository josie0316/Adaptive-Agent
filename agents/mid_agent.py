import traceback
from typing import Tuple

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.mid_planner import MidPlanner
from agents.text_agent import TEXT_ACTION_FAILURE, TEXT_ACTION_SUCCESS, TextAgent


class MidAgent:
    """
    Receive instructions from LLM / Human input, then parse them. Return agent actions
    """

    valid_kwargs = {
        "prepare": ["food", "plate"],
        "assemble": ["food"],
        "pass_on": ["thing", "thing_status"],
        "serve": ["food"],
        "putout_fire": [],
        "clean_a_counter": ["center"],
    }

    def __init__(self, text_action_agent: TextAgent, cooking_world: CookingWorld):
        self.world = cooking_world
        self.text_agent = text_action_agent
        self.agent_idx = self.text_agent.agent_idx
        self.agent = self.text_agent.agent
        self.mid_planner = MidPlanner(self.text_agent, self.world)
        self.prev_text_action = ""

    def update(self, text_action_agent: TextAgent, cooking_world: CookingWorld):
        self.world = cooking_world
        self.text_agent = text_action_agent
        self.agent_idx = self.text_agent.agent_idx
        self.agent = self.text_agent.agent
        self.mid_planner.update(self.text_agent, self.world)

    def get_action(self, func: str, *args, **kwargs) -> Tuple[bool, int, str]:
        """
        Return
        (
            whether the task is finished | bool,
            action, 0 if the task is finished | int,
            execution result | str,
        )
        """
        end = False
        action = TEXT_ACTION_SUCCESS
        text_action = None
        status = ""
        n_max_try = 5
        n_try = 0

        logger.debug(f"args={args}, kwargs={kwargs}")
        valid_kwargs = self.valid_kwargs
        args_str = ",".join(f"'{k}'" if isinstance(k, str) else f"{k}" for k in args) if len(args) > 0 else ""
        kwargs_str = (
            ",".join(f"{k}=" + (f"'{v}'" if isinstance(v, str) else f"{v}") for k, v in kwargs.items())
            if len(kwargs) > 0
            else ""
        )
        logger.debug(f"{func}({(args_str + ', ') if args_str else '' + (kwargs_str if kwargs_str else '')})")
        if not hasattr(self.mid_planner, func):
            end = True
            status = f"Failed, no such action: {func}"
        elif not all([k in valid_kwargs[func] for k in kwargs]):
            end = True
            status = f"Failed, invalid kwargs for {func}: {kwargs_str}"
        elif not len(kwargs) + len(args) <= len(valid_kwargs[func]):
            end = True
            status = f"Failed, too many args for {func}: {args_str + (',' + kwargs_str if kwargs_str else '')}"
        else:
            # perform action
            if self.prev_text_action == "":
                try:
                    (end, text_action) = getattr(self.mid_planner, func)(*args, **kwargs)
                except (TypeError, AttributeError, AssertionError):
                    end = True
                    status = f"Failed, {func}({args_str + (',' + kwargs_str if kwargs_str else '')}) is not valid"
                    tb = traceback.format_exc()
                    logger.error(f"{tb}")
                    # raise e
            else:
                text_action = self.prev_text_action

            while not end and action in [TEXT_ACTION_FAILURE, TEXT_ACTION_SUCCESS]:
                n_try += 1
                if text_action != self.prev_text_action:
                    self.prev_text_action = text_action
                    function, target = self.text_agent.get_instruction(text_action)
                    self.text_agent.update_task(function, target, text_action)
                    logger.debug(f"take text_action {text_action}: {function}, {target}")
                action = self.text_agent.take_one_action()
                logger.trace(f"{action=}")
                if action in [TEXT_ACTION_FAILURE, TEXT_ACTION_SUCCESS]:
                    (end, text_action) = getattr(self.mid_planner, func)(
                        *args,
                        **kwargs,
                        prev_subtask_succeeded=(action == TEXT_ACTION_SUCCESS),
                    )
                    self.prev_text_action = ""
                    if not end:
                        logger.debug(f"next text_action {text_action}")
                    else:
                        logger.debug(f"mid action ended")
                else:
                    break
                if n_try >= n_max_try:
                    end = True
                    text_action = "Failed, too many tries"
                    break
            if end:
                self.prev_text_action = ""
                action = 0
                if status == "":
                    status = text_action
            else:
                status = "Working..."

        assert action in [0, 1, 2, 3, 4, 5], action
        assert not end or ((status.startswith("Succeeded") or status.startswith("Failed")) and action == 0), (
            end,
            action,
            status,
        )

        return end, action, status


if __name__ == "__main__":
    import sys

    from coop_marl.envs.overcooked.overcooked_maker import OvercookedMaker
    from coop_marl.utils import create_parser, parse_args

    logger.remove()
    logger.add(sys.stdout, level="INFO")
    args, conf, env_conf, trainer = parse_args(create_parser())
    env = OvercookedMaker(**env_conf, display=True)
    text_agent = TextAgent(env._env.unwrapped.world, 0)
    mid_agent = MidAgent(env._env.unwrapped.world, text_agent)
    # logger.info(pretty_repr((mid_agent.get_action("hello"))))
    # logger.info(pretty_repr(mid_agent.get_action("prepare", "onion", plate=True)))
    # logger.info(pretty_repr(mid_agent.get_action("prepare", "Beef", plate=True)))
    # logger.info(pretty_repr(mid_agent.get_action("assemble", "Beef")))
    # logger.info(
    #     pretty_repr(mid_agent.get_action("assemble", "Beef", ingredients="Lettuce"))
    # )
    # logger.info(pretty_repr(mid_agent.get_action("assemble", "Beef", True, "Lettuce")))
