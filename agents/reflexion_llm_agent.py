import json
import random

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

# from agents import rule_agent, rule_agent_no_fsm
from agents.react_llm_agent import ReActAgent, ReActAgentNoFSM
from agents.text_agent import TextAgent
from llms.get_llm_output import extract_code_blocks
from prompts.game_prompts import get_reflection_game_prompt, get_task_description
from prompts.instruct_prompts_reflexion import (
    get_reflection_goal_prompt,
    get_reflection_react_goal_prompt,
)


class ReflexionAgentNoFSM(ReActAgentNoFSM):
    """
    Reflexion agent
    """

    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        n_example: int = 2,
        send_message: bool = False,
        receive_message: bool = False,
        max_n_react_turn: int = 3,
        max_n_reflection_event: int = 10,
    ) -> None:
        super().__init__(text_action_agent, cooking_world, n_example, send_message, receive_message, max_n_react_turn)

        self.previous_state: dict = {}
        self.reflection: str = ""
        self.max_n_reflection_event = max_n_reflection_event

    def to_reflection(self, state: dict) -> bool:
        ret = False
        if len(self.previous_state) == 0:
            if state["total_score"] < 0:
                ret = True
        elif state["objects"][("Fire", "")] > 0:
            ret = True
        elif state["total_score"] < self.previous_state["total_score"]:
            ret = True
        self.previous_state = state
        return ret

    def get_llm_input(self, max_event: int, assigned_tasks: bool = True) -> str:
        traj_str = super().get_llm_input(max_event, assigned_tasks)
        traj_str += f"""\
Current Reflection:
{self.reflection}
"""

        return traj_str

    def get_reflection_react_llm_input(self) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
        ## settings of verbal communication
        if self.send_message and self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_BOTH as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.send_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_LLM as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_HUMAN as MESSAGE_SYSTEM_PROMPT,
            )
        else:
            MESSAGE_SYSTEM_PROMPT = ""

        ## add an introduction to game rules before the message system prompt
        game_prompt = get_reflection_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import (  # # basic descriptions of messages (what do you, us and I indicate)
                LATEST_MESSAGE_PROMPT,
                MESSAGE_PROMPT,
            )
        else:
            MESSAGE_PROMPT = ""
            LATEST_MESSAGE_PROMPT = ""

        ## load in all react shots (6 so far) and randomly select 3 of them, each of length 5
        with open("prompts/reflexion_react_examples.json") as f:
            prompt_dict = json.load(f)

        indices = random.sample(range(1, len(prompt_dict) + 1), self.n_example)
        example_strs = ["[Example Begin]\n" + prompt_dict[f"shot {ii}"] + "\n[Example End]" for ii in indices]
        example_prompt = "\n".join(example_strs)

        ## get past react trajectory, and append new observation
        input_prompt = self.get_llm_input(self.max_n_react_turn)

        goal_prompt = get_reflection_react_goal_prompt(
            example_prompt, input_prompt, MESSAGE_PROMPT, LATEST_MESSAGE_PROMPT
        )

        # ## i is the index of react step
        # goal_prompt += f"\nThought {self.react_turn}:"

        user_prompt = "\n".join([game_prompt, goal_prompt])
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def get_reflection_llm_input(self) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
        ## settings of verbal communication
        if self.send_message and self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_BOTH as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.send_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_LLM as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_HUMAN as MESSAGE_SYSTEM_PROMPT,
            )
        else:
            MESSAGE_SYSTEM_PROMPT = ""

        ## add an introduction to game rules before the message system prompt
        game_prompt = get_reflection_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import (  # # basic descriptions of messages (what do you, us and I indicate)
                LATEST_MESSAGE_PROMPT,
                MESSAGE_PROMPT,
            )
        else:
            MESSAGE_PROMPT = ""
            LATEST_MESSAGE_PROMPT = ""

        ## load in all react shots (6 so far) and randomly select 3 of them, each of length 5
        with open("prompts/reflexion_examples.json") as f:
            prompt_dict = json.load(f)

        indices = random.sample(range(1, len(prompt_dict) + 1), self.n_example)
        example_strs = ["[Example Begin]\n" + prompt_dict[f"shot {ii}"] + "\n[Example End]" for ii in indices]
        example_prompt = "\n".join(example_strs)

        ## get past react trajectory, and append new observation
        input_prompt = self.get_llm_input(self.max_n_reflection_event)

        goal_prompt = get_reflection_goal_prompt(example_prompt, input_prompt, MESSAGE_PROMPT, LATEST_MESSAGE_PROMPT)

        user_prompt = "\n".join([game_prompt, goal_prompt])
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def update_reflection(self, llm_output: str) -> None:
        try:
            new_reflection = extract_code_blocks(llm_output, "text")[0].strip()
        except:
            new_reflection = ""
        self.reflection = new_reflection
        self.trajectory = self.trajectory[-1:]

        logger.success(f"Reflexion: {self.reflection}")


class ReflexionAgent(ReActAgent):
    """
    Reflexion agent
    """

    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        n_example: int = 2,
        send_message: bool = False,
        receive_message: bool = False,
        max_n_react_turn: int = 3,
        max_n_reflection_event: int = 10,
    ) -> None:
        super().__init__(text_action_agent, cooking_world, n_example, send_message, receive_message, max_n_react_turn)

        self.previous_state: dict = {}
        self.reflection: str = ""
        self.max_n_reflection_event = max_n_reflection_event

    def to_reflection(self, state: dict) -> bool:
        ret = False
        if len(self.previous_state) == 0:
            if state["total_score"] < 0:
                ret = True
        elif state["objects"][("Fire", "")] > 0:
            ret = True
        elif state["total_score"] < self.previous_state["total_score"]:
            ret = True
        self.previous_state = state.copy()
        return ret

    def get_llm_input(self, max_event: int, assigned_tasks: bool = True) -> str:
        traj_str = super().get_llm_input(max_event, assigned_tasks)
        traj_str += f"""\
Current Reflection:
{self.reflection}
"""

        return traj_str

    def get_reflection_react_llm_input(self) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
        ## settings of verbal communication
        if self.send_message and self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_BOTH as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.send_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_LLM as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_HUMAN as MESSAGE_SYSTEM_PROMPT,
            )
        else:
            MESSAGE_SYSTEM_PROMPT = ""

        ## add an introduction to game rules before the message system prompt
        game_prompt = get_reflection_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import (  # # basic descriptions of messages (what do you, us and I indicate)
                LATEST_MESSAGE_PROMPT,
                MESSAGE_PROMPT,
            )
        else:
            MESSAGE_PROMPT = ""
            LATEST_MESSAGE_PROMPT = ""

        ## load in all react shots (6 so far) and randomly select 3 of them, each of length 5
        with open("prompts/reflexion_react_examples.json") as f:
            prompt_dict = json.load(f)

        indices = random.sample(range(1, len(prompt_dict) + 1), self.n_example)
        example_strs = ["[Example Begin]\n" + prompt_dict[f"shot {ii}"] + "\n[Example End]" for ii in indices]
        example_prompt = "\n".join(example_strs)

        ## get past react trajectory, and append new observation
        input_prompt = self.get_llm_input(self.max_n_react_turn)

        goal_prompt = get_reflection_react_goal_prompt(
            example_prompt, input_prompt, MESSAGE_PROMPT, LATEST_MESSAGE_PROMPT
        )

        # ## i is the index of react step
        # goal_prompt += f"\nThought {self.react_turn}:"

        user_prompt = "\n".join([game_prompt, goal_prompt])
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def get_reflection_llm_input(self) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
        ## settings of verbal communication
        if self.send_message and self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_BOTH as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.send_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_LLM as MESSAGE_SYSTEM_PROMPT,
            )
        elif self.receive_message:
            from prompts.game_prompts import (
                MESSAGE_SYSTEM_PROMPT_ONLY_HUMAN as MESSAGE_SYSTEM_PROMPT,
            )
        else:
            MESSAGE_SYSTEM_PROMPT = ""

        ## add an introduction to game rules before the message system prompt
        game_prompt = get_reflection_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import (  # # basic descriptions of messages (what do you, us and I indicate)
                LATEST_MESSAGE_PROMPT,
                MESSAGE_PROMPT,
            )
        else:
            MESSAGE_PROMPT = ""
            LATEST_MESSAGE_PROMPT = ""

        ## load in all react shots (6 so far) and randomly select 3 of them, each of length 5
        with open("prompts/reflexion_examples.json") as f:
            prompt_dict = json.load(f)

        indices = random.sample(range(1, len(prompt_dict) + 1), self.n_example)
        example_strs = ["[Example Begin]\n" + prompt_dict[f"shot {ii}"] + "\n[Example End]" for ii in indices]
        example_prompt = "\n".join(example_strs)

        ## get past react trajectory, and append new observation
        input_prompt = self.get_llm_input(self.max_n_reflection_event)

        goal_prompt = get_reflection_goal_prompt(example_prompt, input_prompt, MESSAGE_PROMPT, LATEST_MESSAGE_PROMPT)

        user_prompt = "\n".join([game_prompt, goal_prompt])
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def update_reflection(self, llm_output: str) -> None:
        try:
            new_reflection = extract_code_blocks(llm_output, "text")[0].strip()
        except:
            new_reflection = ""
        self.reflection = new_reflection
        self.trajectory = self.trajectory[-1:]

        logger.success(f"Reflexion: {self.reflection}")
