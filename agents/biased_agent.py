from typing import Dict, Tuple

from loguru import logger

from agents.rule_agent_no_fsm import RuleAgentNoFSM


class PrepareBeefAgent(RuleAgentNoFSM):
    prepare = False

    def get_action(self, json_state: Dict) -> Tuple[str, Dict] | None:
        """
        Only prepare beef when necessary.
        Input:
        `json_state`: a dict containing the current state of the game
        """
        if self.prepare:
            self.prepare = False
            return ("pass_on", {"thing": "Beef", "thing_status": "done"})

        objects = json_state["objects"]
        need_beef_num = len([o for o in json_state["orders"] if o["name"] in ["BeefBurger", "BeefLettuceBurger"]])
        have_beef_num = (
            objects.get(("Beef", "In-progress"))
            + objects.get(("Beef", "Well-cooked"))
            + objects.get(("BeefBurger", ""))
            + objects.get(("BeefLettuce", ""))
            + objects.get(("BeefLettuceBurger", ""))
        )
        if have_beef_num < need_beef_num:
            self.prepare = True
            return ("prepare", {"food": "Beef", "plate": True})


class PrepareLettuceAgent(RuleAgentNoFSM):
    prepare = False

    def get_action(self, json_state: Dict) -> Tuple[str, Dict] | None:
        """
        Only prepare Lettuce when necessary.
        Input:
        `json_state`: a dict containing the current state of the game
        """
        if self.prepare:
            self.prepare = False
            return ("pass_on", {"thing": "Lettuce", "thing_status": "done"})
        objects = json_state["objects"]
        need_lettuce_num = len([o for o in json_state["orders"] if o["name"] in ["LettuceBurger", "BeefLettuceBurger"]])
        have_lettuce_num = (
            objects.get(("Lettuce", "Chopped"))
            + objects.get(("LettuceBurger", ""))
            + objects.get(("BeefLettuceBurger", ""))
        )
        if have_lettuce_num < need_lettuce_num:
            self.prepare = True
            return ("prepare", {"food": "Lettuce", "plate": True})


class AssembleServeAgent(RuleAgentNoFSM):
    def get_action(self, json_state: Dict) -> Tuple[str, Dict] | None:
        """
        Only assemble when ready.
        Input:
        `json_state`: a dict containing the current state of the game
        """
        # serve ready burgers
        objects = json_state["objects"]
        orders = [o["name"] for o in json_state["orders"]]
        for o in orders:
            if objects.get((o, "")) > 0:
                return ("serve", {"food": o})
        inventory_other_player = json_state["inventory_other_player"][1 - self.agent_idx]
        recipes = {
            "BeefBurger": [
                [("Beef", "Well-cooked")],
                # [("Beef", "In-progress")],
            ],
            "LettuceBurger": [
                [("Lettuce", "Chopped")],
            ],
            "BeefLettuceBurger": [
                [("Beef", "Well-cooked"), ("Lettuce", "Chopped")],
                # [("Beef", "In-progress"), ("Lettuce", "Chopped")],
                [("BeefLettuce", "")],
            ],
        }

        for order in orders:
            for recipes_order in recipes[order]:
                # for food in recipes_order:
                #     logger.warning(f"{food} {objects.get(food)}")
                if all(
                    [
                        objects.get(food) > 0
                        and not (
                            inventory_other_player
                            and objects.get(food) == 1
                            and {"name": food[0], "status": food[1]} == inventory_other_player
                        )
                        for food in recipes_order
                    ]
                ):
                    # if objects.get(("Bread", "")) > 0 and not (
                    #     inventory_other_player
                    #     and objects.get("Bread", "") == 1
                    #     and {"name": "Bread", "status": ""} == inventory_other_player
                    # ):
                    #     return ("assemble", {"food": order})
                    # else:
                    #     return ("prepare", {"food": "Bread", "plate": True})

                    return ("assemble", {"food": order})


class SwitchAgent:
    def __init__(self, milestones: list[int], agents: list[RuleAgentNoFSM]):
        self.milestones = milestones
        self.agents = agents
        self.current_agent_idx = -1

    def get_action(self, json_state: Dict, step: int) -> Tuple[str, Dict] | None:
        """
        Swith policy accroding to step milestones
        """
        if (
            self.current_agent_idx < len(self.milestones) - 1
            and step >= self.milestones[min(len(self.milestones) - 1, self.current_agent_idx + 1)]
        ):
            self.current_agent_idx += 1
            logger.error(f"Switch to agent {self.current_agent_idx}")
        return self.agents[self.current_agent_idx].get_action(json_state)
