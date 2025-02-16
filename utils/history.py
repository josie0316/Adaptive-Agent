from copy import deepcopy
from pprint import pformat
from typing import Dict, List, NamedTuple, Tuple


class Info(NamedTuple):
    timestep: int
    state: Dict
    message: Dict[int, Dict[int, str]] = {}
    action: Dict[int, Tuple[str, Dict]] = {}


class History:
    def __init__(self, max_steps: int = 1000) -> None:
        self.buffer: List[Info] = []
        self.last_human_action_index: int = 0
        self.max_steps = max_steps

    def reset(self, max_steps: int = 1000) -> None:
        self.buffer = []
        self.last_human_action_index = 0
        self.max_steps = max_steps

    def add(
        self, timestep: int, state: Dict, message: List[Dict[int, str]] = [], action: Dict[int, Tuple[str, Dict]] = {}
    ) -> None:
        self.buffer.append(Info(timestep, state, message, action))

    def add_action(self, action: List[List[str]], index: int) -> None:
        def _action_dict(action: List[List[str]]) -> Dict:
            # match action[0]:
            #     case "prepare":
            #         if action[1] in ["Beef"]:
            #             return (action[0], {"food": action[1], "plate": action[2]})
            #         else:
            #             return (action[0], {"food": action[1]})
            #     case "assemble" | "serve":
            #         return (action[0], {"food": action[1]})
            #     case "pass_on":
            #         return (action[0], {"thing": action[1]})
            #     case "putout_fire":
            #         return (action[0], {})
            if action[0] == "prepare":
                if action[1] in ["Beef"]:
                    return (action[0], {"food": action[1], "plate": action[2]})
                else:
                    return (action[0], {"food": action[1]})
            elif action[0] == "assemble" or action[0] == "serve":
                return (action[0], {"food": action[1]})
            elif action[0] == "pass_on":
                return (action[0], {"thing": action[1]})
            elif action[0] == "putout_fire":
                return (action[0], {})

        self.buffer[self.last_human_action_index].action[index] = _action_dict(action)
        self.last_human_action_index = len(self.buffer) - 1

    def add_message(self, message: str, index: int) -> None:
        self.buffer[-1].message[index] = message

    def get_history(self, length: int) -> List[Info]:
        """
        return history of `length` Infos
        """
        return deepcopy(self.buffer[-length:])

    def get_formatted_history(self, length: int, llm_idx: int) -> str:
        """
        Example:
        Scene {n}:
            State: {state},
            Action: {
                Human: {action_h},
                You: {action_llm}
            },
            Message: {
                Human: {message_h},
                You: {message_llm}
            }
        """

        def indent_text(text, indent_size: int = 8, indent_first_line: bool = False):
            """
            Indents each line of the provided text with the specified indent.
            """
            lines = text.split("\n")
            if indent_first_line:
                return "\n".join(" " * indent_size + line if line.strip() else line for line in lines)
            else:
                return "\n".join(
                    [lines[0]] + [" " * indent_size + line if line.strip() else line for line in lines[1:]]
                )

        formatted_history_template = """\
Scene {scene_n}:
    Remained Timestep: {timestep},
    Score: {score},
    State: {state},
    Action: {action},
    Delivery: {delivery},
    Missed Orders: {missed_orders},
    Message: {message},
"""
        formatted_history = ""
        history = self.get_history(length)
        for i, info in enumerate(history):
            scene_n = max(0, len(self.buffer) - length) + i + 1
            state = deepcopy(info.state)
            if "deliver_log" in state:
                deliver_log = state.pop("deliver_log")
            else:
                deliver_log = []
            total_score = state.pop("total_score")
            delivery = {}
            missed_orders = {}
            for id, name, score, _ in deliver_log:
                if isinstance(id, int):
                    delivery[name] = score
                else:
                    missed_orders[name] = score
            action = {}
            for idx, act in info.action.items():
                if idx == llm_idx:
                    action["You"] = act
                else:
                    action["Human"] = act
            message = {}
            for idx, msg in info.message.items():
                if idx == llm_idx:
                    message["You"] = msg
                else:
                    message["Human"] = msg
            formatted_history += (
                formatted_history_template.format(
                    scene_n=scene_n,
                    timestep=self.max_steps - info.timestep,
                    state=indent_text(pformat(state, compact=True), len("    State: ")),
                    action=pformat(action, compact=True),
                    message=pformat(message, compact=True),
                    delivery=pformat(delivery, compact=True),
                    missed_orders=pformat(missed_orders, compact=True),
                    score=total_score,
                )
                + "\n"
            )
        return formatted_history


if __name__ == "__main__":
    info = Info({"a": 1}, {1: ("a", "b")}, {1: ("c", {"d": 2})})

    print(info)
    print(info._asdict())
