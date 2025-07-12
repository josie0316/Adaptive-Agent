import random
import re
from copy import deepcopy
from typing import Dict, List, Tuple, Union

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.rule_agent import RuleAgent
from agents.rule_agent_no_fsm import RuleAgentNoFSM
from agents.text_agent import TextAgent
from llms.get_llm_output import extract_code_blocks
from prompts.game_prompts import (
    get_reflection_game_prompt,
    get_task_description,
    get_urgent_response_game_prompt,
)
from prompts.instruct_prompts import (
    get_human_inference_output_format_prompt,
    get_reflection_goal_prompt,
    get_reflection_output_format_prompt,
    get_urgent_response_goal_prompt,
    get_urgent_response_output_format_prompt,
)


class CommInferAgent(RuleAgent):
    """
    Conversation-based Inference Agent
    """

    # MESSAGE_TEMPLATE = "I am working on the {orders} order(s), and I am {action_str}."

    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        n_example: int = 10,
        send_message: bool = False,
        receive_message: bool = False,
        infer_human: bool = False,
    ) -> None:
        super().__init__(text_action_agent, cooking_world)
        self.action_in_progress: Union[Tuple[str, Dict], None] = ()
        self.n_example = n_example
        self.send_message = send_message
        self.receive_message = receive_message
        self.infer_human = infer_human

        self.behavior_guideline: str = ""
        self.message: str = ""
        self.inferred_human_behavior_pattern: str = ""

        self.urgent_response_desc: str = ""

        self.text_assign_tasks = []

    def get_action(self, json_state: Dict) -> Tuple[str, Dict] | None:
        self.action_in_progress = super().get_action(json_state)
        return self.action_in_progress

    def get_partner_task_message(self, json_state: Dict) -> str:
        """
        Generate a task assignment message for the partner based on current game state.
        Returns a message like "Can you prepare Lettuce?" or an empty string if no assignment needed.
        """
        orders = json_state.get("orders", [])
        objects = json_state.get("objects", {})
        partner_inventory = json_state.get("inventory_other_player", {})
        pending_tasks = []
        for order in orders:
            order_name = order.get("name", "")
            if order_name == "LettuceBurger":
                if objects.get(("Lettuce", "Chopped"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Lettuce", "priority": 1})
                if objects.get(("Bread", ""), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Bread", "priority": 2})
            elif order_name == "BeefBurger":
                if objects.get(("Beef", "Well-cooked"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Beef", "priority": 1})
                if objects.get(("Bread", ""), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Bread", "priority": 2})
            elif order_name == "BeefLettuceBurger":
                if objects.get(("Beef", "Well-cooked"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Beef", "priority": 1})
                if objects.get(("Lettuce", "Chopped"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Lettuce", "priority": 1})
                if objects.get(("Bread", ""), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Bread", "priority": 2})
        if objects.get(("Fire", ""), 0) > 0:
            return "Can you put out the fire?"
        partner_busy = any(inventory is not None for inventory in partner_inventory.values())
        if partner_busy:
            return ""
        pending_tasks.sort(key=lambda x: x["priority"])
        if pending_tasks:
            task = pending_tasks[0]
            return f"Can you {task['action']} {task['item']}?"
        if objects.get(("Plate", "Empty"), 0) == 0:
            return "Can you get a Plate?"
        return ""

    def get_message(self, json_state: Dict) -> str:
        partner_message = self.get_partner_task_message(json_state)
        if partner_message:
            return partner_message
        # Return empty string instead of using the old template
        return ""

    def get_llm_input(self, history: str, assigned_tasks: bool = True) -> str:
        llm_input = f"""\
History:
{history}
"""
        if assigned_tasks:
            llm_input += f"""\
Current Assigned Tasks:
```json
{self.text_assign_tasks}
```
"""
        llm_input += f"""\
Current Behavior Guidelines:
```json
{self.behavior_guideline}
```
"""
        if self.infer_human:
            llm_input += f"""Inferred Human Behavior:
```json
{self.inferred_human_behavior_pattern}
```
"""
        return llm_input

    def get_reflection_llm_input(self, history: str) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
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
        game_prompt = get_reflection_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import MESSAGE_PROMPT
        else:
            MESSAGE_PROMPT = ""

        # Instructions
        if self.infer_human:
            from prompts.instruct_prompts import INFERRED_HUMAN_PROMPT

            if self.send_message:
                from prompts.instruct_prompts import INFER_HUMAN_WITH_SEND_MESSAGE
            else:
                INFER_HUMAN_WITH_SEND_MESSAGE = ""
            if self.receive_message:
                from prompts.instruct_prompts import INFER_HUMAN_WITH_RECEIVE_MESSAGE
            else:
                INFER_HUMAN_WITH_RECEIVE_MESSAGE = ""
            HUMAN_INFERENCE_OUTPUT_FORMAT = get_human_inference_output_format_prompt(
                infer_human_with_send_message=INFER_HUMAN_WITH_SEND_MESSAGE,
                infer_human_with_receive_message=INFER_HUMAN_WITH_RECEIVE_MESSAGE,
            )
        else:
            INFERRED_HUMAN_PROMPT = ""
            HUMAN_INFERENCE_OUTPUT_FORMAT = ""
        input_prompt = self.get_llm_input(history, False)
        goal_prompt = get_reflection_goal_prompt(
            input_prompt,
            MESSAGE_PROMPT,
            INFERRED_HUMAN_PROMPT,
        )

        output_prompt = get_reflection_output_format_prompt(HUMAN_INFERENCE_OUTPUT_FORMAT)

        user_prompt = "\n".join([game_prompt, goal_prompt, output_prompt])

        messages.append({"role": "user", "content": user_prompt})

        return messages

    def get_urgent_response_llm_input(self, history: str) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
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
        game_prompt = get_urgent_response_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import LATEST_MESSAGE_PROMPT, MESSAGE_PROMPT
        else:
            MESSAGE_PROMPT = ""
            LATEST_MESSAGE_PROMPT = ""

        # Instructions
        if self.infer_human:
            from prompts.instruct_prompts import INFERRED_HUMAN_PROMPT
        else:
            INFERRED_HUMAN_PROMPT = ""

        from prompts.self_reflection_few_shot_examples import (
            example_to_str,
            urgent_response_examples,
        )

        examples = deepcopy(urgent_response_examples)
        random.shuffle(examples)

        example_strs = [example_to_str(example) for example in examples]
        example_prompt = "\n".join(example_strs)

        input_prompt = self.get_llm_input(history)

        goal_prompt = get_urgent_response_goal_prompt(
            example_prompt,
            input_prompt,
            MESSAGE_PROMPT,
            LATEST_MESSAGE_PROMPT,
            INFERRED_HUMAN_PROMPT,
        )

        if self.send_message:
            from prompts.instruct_prompts import MESSAGE_OUTPUT_FORMAT
        else:
            MESSAGE_OUTPUT_FORMAT = ""

        output_prompt = get_urgent_response_output_format_prompt(MESSAGE_OUTPUT_FORMAT)

        user_prompt = "\n".join([game_prompt, goal_prompt, output_prompt])

        messages.append({"role": "user", "content": user_prompt})

        return messages

    def clean_assigned_tasks(self) -> None:
        self.assigned_orders = []
        self.assigned_actions = []

    def update_assigned_tasks(self, llm_output: str) -> None:
        try:
            if "json" in llm_output:
                json_tasks = extract_code_blocks(llm_output)[0].strip()
                json_tasks = json_tasks.replace("false", "False").replace("true", "True")
                assigned_tasks = eval(json_tasks)
            else:
                code_blocks = extract_code_blocks(llm_output, "text")
                json_idx = 1 + self.send_message
                assigned_tasks = eval(code_blocks[json_idx])
        except Exception as e:
            logger.error(f"Error: {e}")
            assigned_tasks = None
        if not isinstance(assigned_tasks, list):
            logger.warning(f"The output format is not correct. Output: {llm_output}")
        else:
            text_outputs = extract_code_blocks(llm_output, language="text")
            if len(text_outputs) > 0:
                self.urgent_response_desc = text_outputs[0].strip()
            else:
                # remove ```json.*``` part and <think>\n .* \n</think> tag by re
                pattern = r"```(?:json).*?```|<think>[\s\S]*?</think>"
                cleaned_output = re.sub(pattern, "", llm_output, flags=re.DOTALL).strip()
                self.urgent_response_desc = cleaned_output
            self.message = text_outputs[1].strip() if len(text_outputs) > 1 else ""
            logger.debug(f"Original Assigned tasks: {assigned_tasks}")
            _assigned_tasks = []
            for task in assigned_tasks:
                if isinstance(task, (list, tuple)):
                    _assigned_tasks.append(tuple(task))
                else:
                    _assigned_tasks.append(str(task))
            assigned_tasks = _assigned_tasks
            # self.text_assign_tasks = deepcopy(assigned_tasks)
            # logger.debug(f"Filtered Assigned tasks: {assigned_tasks}")
            logger.success(f"LLM Urgent Response Thought:\n{self.urgent_response_desc}")
            if self.message:
                logger.debug(f"LLM Message:\n{self.message}")
            logger.success(f"Assigned tasks:\n{assigned_tasks}")
            # logger.success(f"Assigned Tasks:\n{self.assigned_orders}\n{self.assigned_actions}")

            self.text_assign_tasks = self.update_assignments(assigned_tasks)

    def update_reflection(self, llm_output: str) -> None:
        llm_output_blocks = extract_code_blocks(llm_output, language="text")
        if len(llm_output_blocks) == 0:
            self.behavior_guideline = llm_output
        else:
            self.behavior_guideline = llm_output_blocks[0].strip()
        self.inferred_human_behavior_pattern = llm_output_blocks[1].strip() if len(llm_output_blocks) > 1 else ""
        logger.success(f"Behavior Guidelines:\n{self.behavior_guideline}")
        if self.inferred_human_behavior_pattern:
            logger.success(f"Inferred Human Behavior Pattern:\n{self.inferred_human_behavior_pattern}")


class CommInferAgentNoFSM(RuleAgentNoFSM):
    """
    Conversation-based Inference Agent
    """

    # MESSAGE_TEMPLATE = "I am working on the {orders} order(s), and I am {action_str}."

    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        n_example: int = 10,
        send_message: bool = False,
        receive_message: bool = False,
        infer_human: bool = False,
    ) -> None:
        super().__init__(text_action_agent, cooking_world)
        self.action_in_progress: Union[Tuple[str, Dict], None] = ()
        self.n_example = n_example
        self.send_message = send_message
        self.receive_message = receive_message
        self.infer_human = infer_human

        self.behavior_guideline: str = ""
        self.message: str = ""
        self.inferred_human_behavior_pattern: str = ""

        self.urgent_response_desc: str = ""

        self.text_assign_tasks = []

    def get_action(self, json_state: Dict) -> Tuple[str, Dict] | None:
        self.action_in_progress = super().get_action(json_state)
        return self.action_in_progress

    def get_partner_task_message(self, json_state: Dict) -> str:
        """
        Generate a task assignment message for the partner based on current game state.
        Returns a message like "Can you prepare Lettuce?" or an empty string if no assignment needed.
        """
        orders = json_state.get("orders", [])
        objects = json_state.get("objects", {})
        partner_inventory = json_state.get("inventory_other_player", {})
        pending_tasks = []
        for order in orders:
            order_name = order.get("name", "")
            if order_name == "LettuceBurger":
                if objects.get(("Lettuce", "Chopped"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Lettuce", "priority": 1})
                if objects.get(("Bread", ""), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Bread", "priority": 2})
            elif order_name == "BeefBurger":
                if objects.get(("Beef", "Well-cooked"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Beef", "priority": 1})
                if objects.get(("Bread", ""), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Bread", "priority": 2})
            elif order_name == "BeefLettuceBurger":
                if objects.get(("Beef", "Well-cooked"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Beef", "priority": 1})
                if objects.get(("Lettuce", "Chopped"), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Lettuce", "priority": 1})
                if objects.get(("Bread", ""), 0) == 0:
                    pending_tasks.append({"action": "prepare", "item": "Bread", "priority": 2})
        if objects.get(("Fire", ""), 0) > 0:
            return "Can you put out the fire?"
        partner_busy = any(inventory is not None for inventory in partner_inventory.values())
        if partner_busy:
            return ""
        pending_tasks.sort(key=lambda x: x["priority"])
        if pending_tasks:
            task = pending_tasks[0]
            return f"Can you {task['action']} {task['item']}?"
        if objects.get(("Plate", "Empty"), 0) == 0:
            return "Can you get a Plate?"
        return ""

    def get_message(self, json_state: Dict) -> str:
        partner_message = self.get_partner_task_message(json_state)
        if partner_message:
            return partner_message
        # Return empty string instead of using the old template
        return ""

    def get_llm_input(self, history: str, assigned_tasks: bool = True) -> str:
        llm_input = f"""\
History:
{history}
"""
        if assigned_tasks:
            llm_input += f"""\
Current Assigned Tasks:
```json
{self.text_assign_tasks}
```
"""
        llm_input += f"""\
Current Behavior Guidelines:
```json
{self.behavior_guideline}
```
"""
        if self.infer_human:
            llm_input += f"""Inferred Human Behavior:
```json
{self.inferred_human_behavior_pattern}
```
"""
        return llm_input

    def get_reflection_llm_input(self, history: str) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
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
        game_prompt = get_reflection_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import MESSAGE_PROMPT
        else:
            MESSAGE_PROMPT = ""

        # Instructions
        if self.infer_human:
            from prompts.instruct_prompts import INFERRED_HUMAN_PROMPT

            if self.send_message:
                from prompts.instruct_prompts import INFER_HUMAN_WITH_SEND_MESSAGE
            else:
                INFER_HUMAN_WITH_SEND_MESSAGE = ""
            if self.receive_message:
                from prompts.instruct_prompts import INFER_HUMAN_WITH_RECEIVE_MESSAGE
            else:
                INFER_HUMAN_WITH_RECEIVE_MESSAGE = ""
            HUMAN_INFERENCE_OUTPUT_FORMAT = get_human_inference_output_format_prompt(
                infer_human_with_send_message=INFER_HUMAN_WITH_SEND_MESSAGE,
                infer_human_with_receive_message=INFER_HUMAN_WITH_RECEIVE_MESSAGE,
            )
        else:
            INFERRED_HUMAN_PROMPT = ""
            HUMAN_INFERENCE_OUTPUT_FORMAT = ""
        input_prompt = self.get_llm_input(history, False)
        goal_prompt = get_reflection_goal_prompt(
            input_prompt,
            MESSAGE_PROMPT,
            INFERRED_HUMAN_PROMPT,
        )

        output_prompt = get_reflection_output_format_prompt(HUMAN_INFERENCE_OUTPUT_FORMAT)

        user_prompt = "\n".join([game_prompt, goal_prompt, output_prompt])

        messages.append({"role": "user", "content": user_prompt})

        return messages

    def get_urgent_response_llm_input(self, history: str) -> str:
        messages = [{"role": "system", "content": get_task_description()}]

        # Game Settings
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
        game_prompt = get_urgent_response_game_prompt(MESSAGE_SYSTEM_PROMPT)

        if self.send_message or self.receive_message:
            from prompts.instruct_prompts import LATEST_MESSAGE_PROMPT, MESSAGE_PROMPT
        else:
            MESSAGE_PROMPT = ""
            LATEST_MESSAGE_PROMPT = ""

        # Instructions
        if self.infer_human:
            from prompts.instruct_prompts import INFERRED_HUMAN_PROMPT
        else:
            INFERRED_HUMAN_PROMPT = ""

        from prompts.self_reflection_few_shot_examples import (
            example_to_str,
            urgent_response_examples,
        )

        examples = deepcopy(urgent_response_examples)
        random.shuffle(examples)

        example_strs = [example_to_str(example) for example in examples]
        example_prompt = "\n".join(example_strs)

        input_prompt = self.get_llm_input(history)

        goal_prompt = get_urgent_response_goal_prompt(
            example_prompt,
            input_prompt,
            MESSAGE_PROMPT,
            LATEST_MESSAGE_PROMPT,
            INFERRED_HUMAN_PROMPT,
        )

        if self.send_message:
            from prompts.instruct_prompts import MESSAGE_OUTPUT_FORMAT
        else:
            MESSAGE_OUTPUT_FORMAT = ""

        output_prompt = get_urgent_response_output_format_prompt(MESSAGE_OUTPUT_FORMAT)

        user_prompt = "\n".join([game_prompt, goal_prompt, output_prompt])

        messages.append({"role": "user", "content": user_prompt})

        return messages

    def clean_assigned_tasks(self) -> None:
        self.assigned_orders = []
        self.assigned_actions = []

    def update_assigned_tasks(self, llm_output: str) -> None:
        try:
            if "json" in llm_output:
                json_tasks = extract_code_blocks(llm_output)[0].strip()
                json_tasks = json_tasks.replace("false", "False").replace("true", "True")
                assigned_tasks = eval(json_tasks)
            else:
                code_blocks = extract_code_blocks(llm_output, "text")
                json_idx = 1 + self.send_message
                assigned_tasks = eval(code_blocks[json_idx])
        except Exception as e:
            logger.error(f"Error: {e}")
            assigned_tasks = None
        if not isinstance(assigned_tasks, list):
            logger.warning(f"The output format is not correct. Output: {llm_output}")
        else:
            text_outputs = extract_code_blocks(llm_output, language="text")
            if len(text_outputs) > 0:
                self.urgent_response_desc = text_outputs[0].strip()
            else:
                # remove ```json.*``` part and <think>\n .* \n</think> tag by re
                pattern = r"```(?:json).*?```|<think>[\s\S]*?</think>"
                cleaned_output = re.sub(pattern, "", llm_output, flags=re.DOTALL).strip()
                self.urgent_response_desc = cleaned_output
            self.message = text_outputs[1].strip() if len(text_outputs) > 1 else ""
            logger.debug(f"Original Assigned tasks: {assigned_tasks}")
            _assigned_tasks = []
            for task in assigned_tasks:
                if isinstance(task, (list, tuple)):
                    _assigned_tasks.append(tuple(task))
                else:
                    _assigned_tasks.append(str(task))
            assigned_tasks = _assigned_tasks
            # self.text_assign_tasks = deepcopy(assigned_tasks)
            # logger.debug(f"Filtered Assigned tasks: {assigned_tasks}")
            logger.success(f"LLM Urgent Response Thought:\n{self.urgent_response_desc}")
            if self.message:
                logger.debug(f"LLM Message:\n{self.message}")
            logger.success(f"Assigned tasks:\n{assigned_tasks}")
            # logger.success(f"Assigned Tasks:\n{self.assigned_orders}\n{self.assigned_actions}")

            self.text_assign_tasks = self.update_assignments(assigned_tasks)

    def update_reflection(self, llm_output: str) -> None:
        llm_output_blocks = extract_code_blocks(llm_output, language="text")
        if len(llm_output_blocks) == 0:
            self.behavior_guideline = llm_output
        else:
            self.behavior_guideline = llm_output_blocks[0].strip()
        self.inferred_human_behavior_pattern = llm_output_blocks[1].strip() if len(llm_output_blocks) > 1 else ""
        logger.success(f"Behavior Guidelines:\n{self.behavior_guideline}")
        if self.inferred_human_behavior_pattern:
            logger.success(f"Inferred Human Behavior Pattern:\n{self.inferred_human_behavior_pattern}")
