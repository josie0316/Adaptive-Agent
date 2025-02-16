import random
from collections import Counter as CollectionCounter
from copy import deepcopy
from pprint import pformat
from typing import Dict, List, Tuple

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.mid_planner import MidPlanner, get_empty_counter
from agents.text_agent import TextAgent


class RuleAgent:
    """
    Rule-based agent for Cooking, driven by behavior patterns, and assigned orders and actions.
    """

    food_to_ingredients = {
        "BeefBurger": [[("Beef", "Well-cooked")]],
        "LettuceBurger": [[("Lettuce", "Chopped")]],
        "BeefLettuceBurger": [
            [("Beef", "Well-cooked"), ("Lettuce", "Chopped")],
            [("BeefLettuce", "")],
        ],
        "BeefLettuce": [[("Beef", "Well-cooked"), ("Lettuce", "Chopped")]],
    }

    valid_orders = {"BeefBurger", "LettuceBurger", "BeefLettuceBurger"}

    def __init__(self, text_action_agent: TextAgent, cooking_world: CookingWorld) -> None:
        self.world = cooking_world
        self.text_agent = text_action_agent
        self.agent_idx = self.text_agent.agent_idx
        self.mid_planner = MidPlanner(self.text_agent, self.world)

        self.assigned_actions = []
        self.assigned_orders = []
        # self.old_assigned_tasks: list = []
        self.action_patterns = {}
        self.order_patterns = {}
        self.matched_pattern = ()

        self.order_in_progress: List[str] = []  # for output messages
        self.dummy_json_state = None

        self.trajectory: list = []  # store the trajectory of the agent, optional

        self.controlled_by_fsm = False

    def update(self, text_action_agent: TextAgent, cooking_world: CookingWorld, dummy_json_state: Dict = None):
        """
        Binding low-level test_agent and the cooking world
        """
        self.world = cooking_world
        self.text_agent = text_action_agent
        self.agent_idx = self.text_agent.agent_idx
        self.mid_planner.update(self.text_agent, self.world)

        self.assigned_actions = []
        self.assigned_orders = []
        self.action_patterns = {}
        self.order_patterns = {}
        self.matched_pattern = ()

        self.order_in_progress: List[str] = []  # for output messages
        self.dummy_json_state = dummy_json_state

        self.controlled_by_fsm = False

    def update_trajectory(self) -> None:
        """
        Update the trajectory of the agent
        """
        raise NotImplementedError

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
        self.controlled_by_fsm = False
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
                self.controlled_by_fsm = True
        if not mid_action:
            # clean a counter
            n_empty_counter = len(get_empty_counter(self.text_agent, self.world))
            if n_empty_counter <= 0:
                logger.debug("No empty counter detected")
                mid_action = ("clean_a_counter", {"center": False})
                self.controlled_by_fsm = True

        # complete orders
        logger.debug("json state:\n" + pformat(json_state))
        if not self.assigned_orders:
            orders = sorted(json_state["orders"], key=lambda x: x["remain_time"])
            orders = [o["name"] for o in orders]
            # remove all orders that are in other players' inventory
            for obj in json_state["inventory_other_player"].values():
                if obj is not None:
                    obj_name, _ = obj
                    if obj_name in orders:
                        orders.remove(obj_name)
            self.controlled_by_fsm = True
        else:
            current_order_names = [o["name"] for o in json_state["orders"]]
            # avoid the assigned orders that repeat more than the current orders
            self.assigned_orders = self._remove_excess_orders(self.assigned_orders, current_order_names)
            orders = self.assigned_orders
            self.controlled_by_fsm = False

        # urgent mid actions
        if len(self.action_patterns) > 0 and not self.order_in_progress:
            for precond, action in self.action_patterns.items():
                if (precond, action) not in self.assigned_actions:
                    self.assigned_actions.append((precond, action))
        while len(self.assigned_actions) > 0:
            action = self.assigned_actions.pop(0)
            precond, action = action
            if precond(json_state):
                if action[0] not in ["serve"] or action[1]["food"] in orders:
                    mid_action = action
                    self.controlled_by_fsm = False
                    break

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
                        if (
                            action[0] not in ["serve"] or action[1]["food"] in orders
                        ):  # prepare food or serve in-demand food
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

    def _remove_excess_orders(self, selected_orders: List, all_orders: List) -> List:
        """
        Remove the excess orders from the selected orders
        """
        selected_order_counter = CollectionCounter(selected_orders)
        all_order_counter = CollectionCounter(all_orders)
        result = []

        for _o in selected_orders:
            if selected_order_counter[_o] > 0 and all_order_counter.get(_o, -1) > 0:
                result.append(_o)
                selected_order_counter[_o] -= 1
                all_order_counter[_o] -= 1

        return result

    def _prepare_order(self, json_state: Dict, order: str) -> Tuple[str, Dict] | None:
        """
        Prepare the order in default manner
        """
        is_order_ready = json_state["objects"][(order, "")] > 0
        if is_order_ready:
            mid_action = ("serve", {"food": order})
        else:
            is_ingredients_ready = False
            for ingredients in self.food_to_ingredients[order]:
                if all(json_state["objects"][ingredient] > 0 for ingredient in ingredients):
                    is_ingredients_ready = True
                    break
            if is_ingredients_ready:
                mid_action = ("assemble", {"food": order})
            else:
                mid_action = self._prepare_ingredient(json_state, order)
        # assert (
        #     not mid_action or mid_action[1] in MidPlanner.valid_actions[mid_action[0]]
        # ), f"Invalid mid action {mid_action}"
        if not (mid_action[1] in MidPlanner.valid_actions[mid_action[0]]):
            logger.error(f"Invalid mid action {mid_action}")
            mid_action = None

        return mid_action

    def _prepare_ingredient(self, json_state: Dict, food: str) -> Tuple[str, Dict]:
        """
        Prepare the food
        """
        if food in self.food_to_ingredients:
            shuffled_ingredients_list = deepcopy(self.food_to_ingredients[food])
            random.shuffle(shuffled_ingredients_list)
            for ingredients in shuffled_ingredients_list:
                shuffled_ingredients = deepcopy(ingredients)
                random.shuffle(shuffled_ingredients)
                for ingredient in shuffled_ingredients:
                    if json_state["objects"][ingredient] == 0:
                        return self._prepare_ingredient(json_state, ingredient[0])
        else:
            return "prepare", {"food": food, "plate": True if food in ["Beef"] else False}

    def _correct_actions(self, assigned_actions: List) -> Tuple[List, List]:
        """
        Correct the actions, ensure the assigned actions are valid
        """
        assert self.dummy_json_state, "Dummy json state is not provided"
        corrected_actions = []
        text_corrected_actions = []
        for pair in assigned_actions:
            if len(pair) != 2:
                logger.warning(f"Invalid precond-action pair {pair}")
                continue
            try:
                precond, action = pair
                precond = eval(precond)
                if (
                    isinstance(precond(self.dummy_json_state), bool)
                    and action[1] in MidPlanner.valid_actions[action[0]]
                ):
                    corrected_actions.append((precond, action))
                    text_corrected_actions.append(pair)
            except Exception as e:
                logger.error(f"Error in correcting action pair {pair}: {e}")
        return corrected_actions, text_corrected_actions

    def update_assignments(self, assigned_tasks: List = None, behavior_patterns: Dict = None) -> list[str]:
        """
        Update the assignments:
        `assigned_actions`: a list containing some pairs of (precondition, action), each pair is a tuple with the following objects:
            - precondition: a lambda function that takes json_state as input and returns a boolean value, indicating whether the urgent mid action should be executed, given as a string. For example, "lambda json_state: json_state["objects"][("Beef", "Well-cooked")] < 2".
            - action: a tuple containing the action name and the action arguments, the action name is a string, and the action arguments is a dict, valid values are:
                - ("prepare", {"food": "Beef"})
                - ("prepare", {"food": "Beef", "plate": False})
                - ("prepare", {"food": "Lettuce"})
                - ("prepare", {"food": "Bread"})
                - ("assemble", {"food": "LettuceBurger"})
                - ("assemble", {"food": "BeefBurger"})
                - ("assemble", {"food": "BeefLettuceBurger"})
                - ("pass_on", {"thing": "Plate"})
                # Rule-based decision for which burger to serve ?
                - ("serve", {"food": "BeefBurger"})
                - ("serve", {"food": "LettuceBurger"})
                - ("serve", {"food": "BeefLettuceBurger"})
                - ("putout_fire", {})

        `assigned_orders`: a list containing names of the orders to be complete in sequence, it is a subset of the orders in json_state.

        `behavior_patterns`: a dict containing patterns to complete the orders and patterns for specific actions
            - When the keys are tuples of order names which need to be complete in sequence, the values are the corresponding preconditions and actions or simply the order names to complete the orders. In the values, the format of preconditions and actions is as the same in `assigned_actions` parameter. Order names in the values mean the agent will complete the orders following the default policy. The actions will be repeated until the preconditions are not satisfied.
            - When the keys are pre-conditions, the values are the corresponding actions.
        An example is:
            ```
            {
                ("BeefBurger", "BeefBurger"): [
                    ("lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] < 2", ("prepare", {"food": "Beef"})),
                    ("lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] < 2", ("prepare", {"food": "Beef"})),
                    ("lambda json_state: True", ("assemble", {"food": "BeefBurger"})),
                    ("lambda json_state: True", ("serve", {"food": "BeefBurger"})),
                    ("lambda json_state: True", ("assemble", {"food": "BeefBurger"})),
                    ("lambda json_state: True", ("serve", {"food": "BeefBurger"})),
                ],
                lambda json_state: json_state["objects"][("Beef", "Well-cooked")] < 2: ("prepare", {"food": "Beef"}),
            }
            ```
            The food name "BeefLettuce" also means that the agent will prepare the BeefLettuce in default mode.
            If the order tuples overlap, the order tuple matches a maximum of current orders will be selected.
        """
        text_assigned_tasks = []
        if assigned_tasks:
            self.assigned_actions = []
            self.assigned_orders = []
            for task in assigned_tasks:
                #    if (
                #        task in self.old_assigned_tasks
                #        and task not in self.assigned_actions
                #        and task not in self.assigned_orders
                #    ):
                #        continue
                if isinstance(task, str):
                    if task in self.valid_orders:
                        self.assigned_orders.append(task)
                        text_assigned_tasks.append(task)
                    else:
                        logger.warning(f"Invalid order name {task} in order patterns")
                elif isinstance(task, (tuple,)) and len(task) == 2:
                    self.assigned_actions.append(task)
                    # text_assigned_tasks.append(task)
                else:
                    logger.warning(f"Invalid task {task} in assigned")
            self.assigned_actions, text_actions = self._correct_actions(self.assigned_actions)
            # self.old_assigned_tasks = deepcopy(self.assigned_actions + self.assigned_orders)
            text_assigned_tasks += text_actions

        if behavior_patterns:
            behavior_patterns = deepcopy(behavior_patterns)
            self.action_patterns = {}
            self.order_patterns = {}
            for o_t in behavior_patterns:

                if isinstance(o_t, tuple):
                    if not set(o_t).issubset(self.valid_orders):
                        logger.warning(f"Invalid order tuple {o_t} in order patterns")
                        continue
                    pattern = []
                    for a_o in behavior_patterns[o_t]:
                        if isinstance(a_o, str):
                            if a_o in self.food_to_ingredients:
                                pattern.append(a_o)
                        else:
                            corrected = self._correct_actions([a_o])
                            if len(corrected) > 0:
                                pattern.append(corrected[0])
                    self.order_patterns[o_t] = pattern
                elif isinstance(o_t, str):
                    corrected = self._correct_actions([(o_t, behavior_patterns[o_t])])
                    if len(corrected) > 0:
                        self.action_patterns[corrected[0][0]] = corrected[0][1]
            self.matched_pattern = ()
        return text_assigned_tasks
