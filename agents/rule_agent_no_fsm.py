from copy import deepcopy
from pprint import pformat
from typing import Dict, Tuple

from loguru import logger

from agents import rule_agent
from agents.mid_planner import get_empty_counter


class RuleAgentNoFSM(rule_agent.RuleAgent):
    """
    Rule-based agent for Cooking, driven by behavior patterns, and assigned orders and actions.
    """

    def get_action(self, json_state: Dict, enhanced: bool = False) -> Tuple[str, Dict] | None:
        """
        Input:
        `json_state`: a dict containing the current state of the game, with the following keys:
            - objects: a dict recording the number of objects with different status, mapping from (object_name, object_status) to object_number. Pay attention that when the object_number is 0 for an object with status as "Fresh", you can get the object from the distribution station.
            - orders: a list containing the orders, the order is a dict with the following objects as keys:
                - name: the name of the order, valid orders contains "BeefBurger", "LettuceBurger", "BeefLettuceBurger".
                - remain_time: the remaining time for completing the order, smaller remain_time means the order is more urgent.
            - inventory_other_player: a dict recording the objects held by the other player, mapping from other_agent_id to (object_name, object_status).
            - deliver_log: a dict recording the objects delivered by the other player, mapping from other_agent_id to object_name.
            Example:
                {
                    "objects": {
                        ("Beef", "Fresh"): ...,
                        ("Beef", "In-progress"): ...,
                        ("Beef", "Well-cooked"): ...,
                        ("Beef", "Overcooked"): ...,
                        ("Lettuce", "Unchopped"): ...,
                        ("Lettuce", "Chopped"): ...,
                        ("Bread", ""): ...,
                        ("BeefLettuce", ""): ...,
                        ("BeefBurger", ""): ...,
                        ("LettuceBurger", ""): ...,
                        ("BeefLettuceBurger", ""): ...
                        ("Plate", "Empty"): ...,
                        ("FireExtinguisher", ""): ...,
                        ("Fire", ""): ...,
                    },
                    "orders": [
                        {
                            "name": ...,
                            "remain_time": ...
                        },
                        ...
                    ],
                    "inventory_other_player": {
                        other_agent_id0: (Object_name, Object_status),
                        other_agent_id1: (Object_name, Object_status),
                        ...
                    },
                    "deliver_log": [
                        (agent_id, Object_name, Score),
                        ...
                        ("Missed", Object_name, Score)
                    ]
                }
        """
        # update assigned_order
        if self.agent_idx in [t[0] for t in json_state["deliver_log"]]:
            for idx, food, _, _ in json_state["deliver_log"]:
                if idx != self.agent_idx:
                    continue
                if food in self.valid_orders:
                    if food in self.assigned_orders:
                        self.assigned_orders.remove(food)
                    if self.matched_pattern and food in self.matched_pattern[1]:
                        self.matched_pattern[1].remove(food)
                    if food in self.order_in_progress:
                        self.order_in_progress.remove(food)

        mid_action = None
        if enhanced:
            # fire
            if json_state["objects"][("Fire", "")] > 0:
                logger.debug("Fire detected")
                mid_action = ("putout_fire", {})
        if not mid_action:
            # clean a counter
            n_empty_counter = len(get_empty_counter(self.text_agent, self.world))
            if n_empty_counter <= 0:
                logger.debug("No empty counter detected")
                mid_action = ("clean_a_counter", {"center": False})

        # complete orders
        ## when there are no assigned orders: get orders that are not in other's inventory
        ## the orders are sorted based on remaining time
        logger.debug("json state:\n" + pformat(json_state))
        if not self.assigned_orders:
            """
            orders = sorted(json_state["orders"], key=lambda x: x["remain_time"])
            orders = [o["name"] for o in orders]
            # remove all orders that are in other players' inventory
            for obj in json_state["inventory_other_player"].values():
                if obj is not None:
                    obj_name, _ = obj
                    if obj_name in orders:
                        orders.remove(obj_name)
            """
            orders = []
        ## delete excessive orders in assigned orders
        else:
            # current_order_names = [o["name"] for o in json_state["orders"]]
            # avoid the assigned orders that repeat more than the current orders
            # self.assigned_orders = self._remove_excess_orders(self.assigned_orders, current_order_names)
            orders = self.assigned_orders

        # urgent mid actions
        if len(self.action_patterns) > 0 and not self.order_in_progress:
            for precond, action in self.action_patterns.items():
                if (precond, action) not in self.assigned_actions:
                    self.assigned_actions.append((precond, action))

        ## first complete all assigned actions
        while len(self.assigned_actions) > 0:
            action = self.assigned_actions.pop(0)
            precond, action = action
            try:
                if precond(json_state):
                    # if action[0] not in ["serve"] or action[1]["food"] in orders:
                    #     mid_action = action
                    #     break
                    mid_action = action
                    break
            except Exception as e:
                logger.error(f"Error in assigned action {action}: {e}")

        log_data = {
            "orders": orders,
            "order tuples to match": list(self.order_patterns.keys()),
            "matched pattern": self.matched_pattern,
        }
        if mid_action:
            log_data["assigned action"] = (precond, action)
        logger.debug("process info:\n" + pformat(log_data))

        if mid_action:
            # assert mid_action[1] in MidPlanner.valid_actions[mid_action[0]], "Invalid mid action"
            self.order_in_progress = []
            return mid_action

        if len(orders) > 0:
            if not self.matched_pattern:
                order_tuples = sorted(list(self.order_patterns.keys()), key=len, reverse=True)
                for o_t in order_tuples:
                    if orders[: len(o_t)] == list(o_t):
                        self.matched_pattern = (o_t, deepcopy(self.order_patterns[o_t]))
                        logger.debug(
                            f"Preparing orders {self.matched_pattern[0]} using\n{pformat(self.matched_pattern[1])}"
                        )
                        self.order_in_progress = list(self.matched_pattern[0])
                        break
            while self.matched_pattern and len(self.matched_pattern[1]) > 0:
                a_o = self.matched_pattern[1].pop(0)
                if isinstance(a_o, str) and a_o in orders:  # prepare the food in default mode
                    order = a_o
                    mid_action = self._prepare_order(json_state, order)
                    self.matched_pattern[1].insert(0, order)
                    break
                elif isinstance(a_o, tuple):
                    precond, action = a_o
                    if precond(json_state):
                        # if (
                        #     action[0] not in ["serve"] or action[1]["food"] in orders
                        # ):  # prepare food or serve in-demand food
                        #     mid_action = action
                        #     self.matched_pattern[1].insert(0, a_o)
                        #     break
                        mid_action = action
                        self.matched_pattern[1].insert(0, a_o)
                        break
            else:  # no break means the matched orders are completed
                self.matched_pattern = ()
            if not mid_action:
                self.order_in_progress = [orders[0]]
                mid_action = self._prepare_order(json_state, orders[0])

        # assert (
        #     not mid_action or mid_action[1] in MidPlanner.valid_actions[mid_action[0]]
        # ), f"Invalid mid action {mid_action}"
        return mid_action
