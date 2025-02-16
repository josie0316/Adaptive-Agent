from typing import Dict, Tuple, Union

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents import rule_agent_no_fsm
from agents.text_agent import TextAgent
from llms.get_llm_output_act import get_openai_llm_output
from prompts.instruct_prompts_act import get_act_goal_prompt


class LLMActionAgent(rule_agent_no_fsm.RuleAgentNoFSM):
    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        model: str,
        params: dict,
        max_action_history: int = 5,
    ) -> None:
        super().__init__(text_action_agent, cooking_world)
        self.action_in_progress: Union[Tuple[str, Dict], None] = ()

        self.model = model
        self.params = params

        self.act_turn = 1
        self.max_action_history = max_action_history

        self.trajectory: list[dict[str, str]] = []  # {"Observation": str, "Action": str, "Result": str}

    async def warm_start(self) -> None:
        # load models
        return await get_openai_llm_output(
            [{"role": "system", "content": "Hello! Who are you?"}], self.model, self.params
        )

    ## get action to take based on pre-defined rules (finite state machine) as well as assigned tasks
    async def get_action(self, scene: str) -> Tuple[str | Dict]:
        messages, goal_prompt = self.get_act_llm_input(scene)

        action = await get_openai_llm_output(messages, self.model, self.params)

        if action:
            action = action.action
            act_type = type(action).__name__
            match act_type:
                case "prepare":
                    action_dict = {"food": action.food.value, "plate": action.plate}
                case "assemble":
                    action_dict = {"food": action.food.value}
                case "serve":
                    action_dict = {"food": action.food.value}
                case "putout_fire":
                    action_dict = {}
                case "pass_on":
                    action_dict = {
                        "thing": action.thing_status_pair.value.split("_")[0],
                        "thing_status": action.thing_status_pair.value.split("_")[1],
                    }
                case "clean_a_counter":
                    action_dict = {"center": False}
                case _:
                    logger.error(f"unknownactiontype: {act_type}")
                    return None

            action = (act_type, action_dict)

        self.trajectory.append({"Observation": scene, "Action": action})

        self.act_turn += 1

        return action, goal_prompt

    def store_result(self, result: str) -> None:
        self.trajectory[-1]["Result"] = result

    def get_message(self, json_state: Dict) -> str:
        raise NotImplementedError("ReActAgent does not support sending messages.")

    def get_llm_input(self, scene: str, max_event: int) -> str:
        tmp_traj = self.trajectory[-max_event:]
        traj_str = ""

        for turn, shot in zip(range(max(0, self.act_turn - len(tmp_traj)) + 1, self.act_turn + 1), tmp_traj):
            traj_str += f"Observation {turn}:\n {shot['Observation']}\n"
            traj_str += f"Action {turn}:\n {shot['Action']}\n"
            if "Result" in shot:
                traj_str += f"Action {turn} Result:\n {shot['Result']}\n\n\n"
            else:
                traj_str += f"Action {turn} Result:\n Unknown\n\n\n"

        traj_str += f"Current Observation:\n {scene}\n"

        return traj_str

    def get_act_llm_input(self, scene: str) -> str:
        messages = []

        input_prompt = self.get_llm_input(scene, self.max_action_history)

        goal_prompt = get_act_goal_prompt(input_prompt)

        messages.append({"role": "user", "content": goal_prompt})

        logger.info(f"LLM input: {goal_prompt}")

        return messages, goal_prompt
