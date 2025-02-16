import json
import random
import re
from typing import Dict, Tuple, Union

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents import rule_agent, rule_agent_no_fsm
from agents.text_agent import TextAgent
from llms.get_llm_output import extract_code_blocks
from prompts.game_prompts import get_reflection_game_prompt, get_task_description
from prompts.instruct_prompts_react import get_react_goal_prompt


class ReActAgentNoFSM(rule_agent_no_fsm.RuleAgentNoFSM):
    """
    ReAct agent
    """

    MESSAGE_TEMPLATE = "I am working on the {orders} order(s), and I am {action_str}."

    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        n_example: int = 2,
        send_message: bool = False,
        receive_message: bool = False,
        max_n_react_turn: int = 5,
    ) -> None:
        super().__init__(text_action_agent, cooking_world)
        self.action_in_progress: Union[Tuple[str, Dict], None] = ()
        self.n_example = n_example
        self.send_message = send_message
        self.receive_message = receive_message

        self.message: str = ""
        self.react_thought: str = ""

        self.text_assign_tasks = []

        self.react_turn = 1
        self.max_n_react_turn = max_n_react_turn
        self.trajectory: list[dict[str, str]] = []

    def update_trajectory(self, scene: str) -> None:
        self.trajectory.append({"Observation": scene})

    ## get action to take based on pre-defined rules (finite state machine) as well as assigned tasks
    def get_action(self, json_state: Dict) -> Tuple[str | Dict]:
        self.action_in_progress = super().get_action(json_state)
        return self.action_in_progress

    def get_message(self, json_state: Dict) -> str:
        raise NotImplementedError("ReActAgent does not support sending messages.")

    def get_llm_input(self, max_event: int, assigned_tasks: bool = True) -> str:
        # ! mark: input scene
        tmp_traj = self.trajectory[-max_event:]
        traj_str = ""

        for turn, shot in zip(range(max(0, self.react_turn - len(tmp_traj)) + 1, self.react_turn + 1), tmp_traj):
            traj_str += f"Observation {turn}:\n {shot['Observation']}\n"
            if "Thought" in shot:
                traj_str += f"Thought {turn}:\n {shot['Thought']}\n"
            if "Action" in shot:
                traj_str += f"Action {turn}:\n {shot['Action']}\n\n\n"
        if assigned_tasks:
            traj_str += f"""\
Current Assigned Tasks:
```json
{self.text_assign_tasks}
```
"""

        return traj_str

    def get_react_llm_input(self) -> str:
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
        with open("prompts/react_examples.json") as f:
            prompt_dict = json.load(f)

        indices = random.sample(range(1, len(prompt_dict) + 1), self.n_example)
        example_strs = ["[Example Begin]\n" + prompt_dict[f"shot {ii}"] + "\n[Example End]\n\n" for ii in indices]
        example_prompt = "\n".join(example_strs)

        ## get past react trajectory, and append new observation
        input_prompt = self.get_llm_input(self.max_n_react_turn)

        goal_prompt = get_react_goal_prompt(example_prompt, input_prompt, MESSAGE_PROMPT, LATEST_MESSAGE_PROMPT)

        # ## i is the index of react step
        # goal_prompt += f"\nThought {self.react_turn}:"

        user_prompt = "\n".join([game_prompt, goal_prompt])
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def clean_assigned_tasks(self) -> None:
        self.assigned_orders = []
        self.assigned_actions = []

    # update self.trajectory and self.react_turn
    def update_react(self, new_thought, new_action):
        self.trajectory[-1]["Thought"] = new_thought
        self.trajectory[-1]["Action"] = new_action
        # self.trajectory += f"\nThought {self.react_turn}: {new_thought} \nAction {self.react_turn}: {new_action} "
        self.react_turn += 1

    ## does not support sending message so far
    def update_assigned_tasks(self, llm_output: str) -> None:
        if "json" in llm_output:
            # print(extract_code_blocks(llm_output)[0])
            try:
                json_tasks = extract_code_blocks(llm_output)[0].strip()
                json_tasks = json_tasks.replace("false", "False").replace("true", "True")
                assigned_tasks = eval(json_tasks)
                logger.debug(f"Original Assigned tasks: {assigned_tasks}")
                self.text_assign_tasks = []
                _assigned_tasks = []
                for task in assigned_tasks:
                    if isinstance(task, (list, tuple)):
                        _assigned_tasks.append(tuple(task))
                    else:
                        _assigned_tasks.append(str(task))
                assigned_tasks = _assigned_tasks
                # self.text_assign_tasks = deepcopy(assigned_tasks)
                self.text_assign_tasks = self.update_assignments(assigned_tasks)
                logger.success(f"Assigned tasks:\n{self.text_assign_tasks}")
            except Exception as e:
                logger.error(e)
                logger.warning(f"Action generated:\n{llm_output}")
                logger.warning("The action format is incorrect. ")
                return None
            try:
                text_outputs = extract_code_blocks(llm_output, language="text")
                if len(text_outputs) > 0:
                    self.react_thought = text_outputs[0].strip()
                else:
                    # remove ```json.*``` part and <think>\n .* \n</think> tag by re
                    pattern = r"```(?:json).*?```|<think>[\s\S]*?</think>"
                    cleaned_output = re.sub(pattern, "", llm_output, flags=re.DOTALL).strip()
                    self.react_thought = cleaned_output
                logger.success(f"React Thought: {self.react_thought}")
                return (text_outputs, self.text_assign_tasks)
            except Exception as e:
                logger.error(e)
                logger.warning(f"Thought generated:\n{llm_output}")
                logger.warning("The thought format is incorrect. ")
                return None
        else:
            logger.warning("The action format is incorrect. ")
            return None


class ReActAgent(rule_agent.RuleAgent):
    """
    ReAct agent
    """

    MESSAGE_TEMPLATE = "I am working on the {orders} order(s), and I am {action_str}."

    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        n_example: int = 2,
        send_message: bool = False,
        receive_message: bool = False,
        max_n_react_turn: int = 5,
    ) -> None:
        super().__init__(text_action_agent, cooking_world)
        self.action_in_progress: Union[Tuple[str, Dict], None] = ()
        self.n_example = n_example
        self.send_message = send_message
        self.receive_message = receive_message

        self.message: str = ""
        self.react_thought: str = ""

        self.text_assign_tasks = []

        self.react_turn = 1
        self.max_n_react_turn = max_n_react_turn
        self.trajectory: list[dict[str, str]] = []

    def update_trajectory(self, scene: str) -> None:
        self.trajectory.append({"Observation": scene})

    ## get action to take based on pre-defined rules (finite state machine) as well as assigned tasks
    def get_action(self, json_state: Dict) -> Tuple[str | Dict]:
        self.action_in_progress = super().get_action(json_state)
        return self.action_in_progress

    def get_message(self, json_state: Dict) -> str:
        raise NotImplementedError("ReActAgent does not support sending messages.")

    def get_llm_input(self, max_event: int, assigned_tasks: bool = True) -> str:
        # ! mark: input scene
        tmp_traj = self.trajectory[-max_event:]
        traj_str = ""

        for turn, shot in zip(range(max(0, self.react_turn - len(tmp_traj)) + 1, self.react_turn + 1), tmp_traj):
            traj_str += f"Observation {turn}:\n {shot['Observation']}\n"
            if "Thought" in shot:
                traj_str += f"Thought {turn}:\n {shot['Thought']}\n"
            if "Action" in shot:
                traj_str += f"Action {turn}:\n {shot['Action']}\n\n\n"
        if assigned_tasks:
            traj_str += f"""\
Current Assigned Tasks:
```json
{self.text_assign_tasks}
```
"""

        return traj_str

    def get_react_llm_input(self) -> str:
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
        with open("prompts/react_examples.json") as f:
            prompt_dict = json.load(f)

        indices = random.sample(range(1, len(prompt_dict) + 1), self.n_example)
        example_strs = ["[Example Begin]\n" + prompt_dict[f"shot {ii}"] + "\n[Example End]\n\n" for ii in indices]
        example_prompt = "\n".join(example_strs)

        ## get past react trajectory, and append new observation
        input_prompt = self.get_llm_input(self.max_n_react_turn)

        goal_prompt = get_react_goal_prompt(example_prompt, input_prompt, MESSAGE_PROMPT, LATEST_MESSAGE_PROMPT)

        # ## i is the index of react step
        # goal_prompt += f"\nThought {self.react_turn}:"

        user_prompt = "\n".join([game_prompt, goal_prompt])
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def clean_assigned_tasks(self) -> None:
        self.assigned_orders = []
        self.assigned_actions = []

    # update self.trajectory and self.react_turn
    def update_react(self, new_thought, new_action):
        self.trajectory[-1]["Thought"] = new_thought
        self.trajectory[-1]["Action"] = new_action
        # self.trajectory += f"\nThought {self.react_turn}: {new_thought} \nAction {self.react_turn}: {new_action} "
        self.react_turn += 1

    ## does not support sending message so far
    def update_assigned_tasks(self, llm_output: str) -> None:
        if "json" in llm_output:
            # print(extract_code_blocks(llm_output)[0])
            try:
                json_tasks = extract_code_blocks(llm_output)[0].strip()
                json_tasks = json_tasks.replace("false", "False").replace("true", "True")
                assigned_tasks = eval(json_tasks)
                logger.debug(f"Original Assigned tasks: {assigned_tasks}")
                self.text_assign_tasks = []
                _assigned_tasks = []
                for task in assigned_tasks:
                    if isinstance(task, (list, tuple)):
                        _assigned_tasks.append(tuple(task))
                    else:
                        _assigned_tasks.append(str(task))
                assigned_tasks = _assigned_tasks
                # self.text_assign_tasks = deepcopy(assigned_tasks)
                self.text_assign_tasks = self.update_assignments(assigned_tasks)
                logger.success(f"Assigned tasks:\n{self.text_assign_tasks}")
                text_outputs = extract_code_blocks(llm_output, language="text")
                if len(text_outputs) > 0:
                    self.react_thought = text_outputs[0].strip()
                else:
                    # remove ```json.*``` part and <think>\n .* \n</think> tag by re
                    pattern = r"```(?:json).*?```|<think>[\s\S]*?</think>"
                    cleaned_output = re.sub(pattern, "", llm_output, flags=re.DOTALL).strip()
                    self.react_thought = cleaned_output
                logger.success(f"React Thought: {self.react_thought}")
                return (text_outputs, self.text_assign_tasks)
            except Exception as e:
                logger.error(e)
                logger.warning("The action format is incorrect. ")
                return None
        else:
            logger.warning("The action format is incorrect. ")
            return None
