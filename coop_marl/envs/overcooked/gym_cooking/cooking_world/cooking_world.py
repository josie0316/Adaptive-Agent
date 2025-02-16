import json
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
from gym_cooking.cooking_world.world_objects import *
from loguru import logger

MIXABLE_INGREDS = {
    "Lettuce": ["Tomato", "Onion", "OnionTomato", "Bread", "Beef", "BeefBurger"],
    "Tomato": ["Lettuce", "Carrot", "LettuceOnion"],
    "Onion": ["Lettuce", "Tomato", "LettuceTomato"],
    "LettuceTomato": ["Onion"],
    "OnionTomato": ["Lettuce"],
    "LettuceOnion": ["Tomato"],
    "Beef": ["Lettuce", "Bread", "LettuceBurger"],
    "Bread": ["Beef", "Lettuce", "BeefLettuce"],
    "BeefBurger": ["Lettuce"],
    "LettuceBurger": ["Beef"],
    "BeefLettuceBurger": [],
    "BeefLettuce": ["Bread"],
}

EVENT_LIST = [
    "get_lettuce_from_station",
    "get_beef_from_station",
    "get_bread_from_station",
    "get_plate_from_station",
    "put_onto_pan",
    "put_onto_cutboard",
    "put_onto_center_counter",
    "put_onto_counter",
    "put_onto_plate",
    "deliver_burger",
    "drop_food",
    "chop_lettuce(done)",
    "chop_lettuce(doing)",
    "pickup_plate",
    "pickup_beef_overcooked",
    "pickup_beef_done",
    "pickup_beef_fresh",
    "pickup_lettuce_in_plate",
    "pickup_bread_in_plate",
    "pickup_beefburger",
    "pickup_lettuceburger",
    "pickup_beeflettuceburger",
    "pickup_beeflettuce",
    "pickup_lettuce_done",
    "pickup_lettuce_fresh",
    "pickup_bread",
    "pickup_fireextinguisher",
    "put_out_fire(doing)",
    "put_out_fire(done)",
]


def is_mixable(food, container):
    if len(container.content) == 0:
        return not getattr(food, "fresh", lambda: False)()
    if all([is_food_mixable(food, c_food) for c_food in container.content]):
        return True
    return False


def is_food_mixable(food1, food2):
    food1_name = type(food1).__name__
    food2_name = type(food2).__name__
    # logger.trace(f"Mixing {food1_name} and {food2_name}")
    if food1_name in MIXABLE_INGREDS[food2_name] or food2_name in MIXABLE_INGREDS[food1_name]:
        if isinstance(food1, ChopFood) and isinstance(food2, ChopFood):
            return food1.chop_state == ChopFoodStates.CHOPPED and food2.chop_state == ChopFoodStates.CHOPPED
        elif isinstance(food1, ChopFood) and isinstance(food2, BlenderFood):
            if isinstance(food2, Beef):
                return food1.chop_state == ChopFoodStates.CHOPPED and food2.blend_state == BlenderFoodStates.MASHED
            else:
                return food1.chop_state == ChopFoodStates.CHOPPED and food2.blend_state == BlenderFoodStates.FRESH
        elif isinstance(food1, BlenderFood) and isinstance(food2, ChopFood):
            if isinstance(food1, Beef):
                return food1.blend_state == BlenderFoodStates.MASHED and food2.chop_state == ChopFoodStates.CHOPPED
            else:
                return food1.blend_state == BlenderFoodStates.FRESH and food2.chop_state == ChopFoodStates.CHOPPED
        elif isinstance(food1, Food) and isinstance(food2, ChopFood):
            return food2.chop_state == ChopFoodStates.CHOPPED
        elif isinstance(food1, ChopFood) and isinstance(food2, Food):
            return food1.chop_state == ChopFoodStates.CHOPPED
        elif isinstance(food1, BlenderFood) and isinstance(food2, Food):
            return food1.blend_state == BlenderFoodStates.MASHED
        elif isinstance(food1, Food) and isinstance(food2, BlenderFood):
            return food2.blend_state == BlenderFoodStates.MASHED
        elif isinstance(food1, Food) and isinstance(food2, Food):
            return True

    return False


class CookingWorld:
    # COLORS = ["blue", "magenta", "yellow", "green"]

    # unused
    # SymbolToClass = {
    #     ' ': Floor,
    #     '-': Counter,
    #     '/': CutBoard,
    #     '*': DeliverSquare,
    #     't': Tomato,
    #     'l': Lettuce,
    #     'o': Onion,
    #     'p': Plate,
    #     'b': Blender
    # }

    # AGENT_ACTIONS: 0: Noop, 1: Left, 2: right, 3: down, 4: up, 5: interact

    def __init__(self, agent_type=0):
        if agent_type == 0:
            self.COLORS = ["blue", "magenta", "red", "green"]
        else:
            self.COLORS = ["blue", "red", "magenta", "green"]
        self.agents = []
        self.level_array = [[]]
        self.width = 0
        self.height = 0
        self.world_objects = defaultdict(list)
        self.abstract_index = defaultdict(list)
        self.prev_world: CookingWorld = None
        self.prev_holding = []
        self.deliver_log: list[tuple[int | str, str, int, dict]] = []
        # (idx, name, score)

    def perceive_agent_event(self, idx) -> Union[str, None]:
        agent: Agent = self.agents[idx]
        if len(agent.event_list) == 0:
            return None
        return agent.event_list[-1]

    def perceive_events(self) -> Dict[int, Union[str, None]]:
        events = {}
        for i, agent in enumerate(self.agents):
            event = self.perceive_agent_event(i)
            events[i] = event
        return events

    def get_events(self) -> Dict[int, List[str]]:
        return {agent_id: agent.event_list.copy() for agent_id, agent in enumerate(self.agents)}

    def get_mid_actions(self) -> Dict[int, List[str]]:
        agent_holding = None

        def _one_step_work(event_now: str):
            nonlocal agent_holding
            mid_action = None
            # prepare lettuce
            if event_now == "chop_lettuce(done)":
                mid_action = ["prepare", "lettuce", "false"]
            elif event_now == "plate_lettuce_done_from_cutboard":
                mid_action = ["prepare", "lettuce", "true"]
            elif event_now == "put_lettuce_onto_plate":
                mid_action = ["prepare", "lettuce", "true"]

            # prepare beef
            elif event_now == "plate_beef_done_from_pan":
                mid_action = ["prepare", "beef", "true"]

            # pass_on
            elif event_now.startswith("pass_on"):
                infos = event_now.split("_")
                if len(infos) == 3:
                    mid_action = ["pass_on", infos[2]]
                else:
                    mid_action = ["pass_on", infos[2], infos[3]]

            # putout fire
            elif event_now == "put_out_fire(done)":
                mid_action = ["putout_fire"]

            return mid_action

        def _two_step_action(event_now: str, event_last: str):
            nonlocal agent_holding
            agent_holding = None
            mid_action = None
            # prepare bread
            if event_now == "put_bread_onto_plate" and event_last == "get_bread_from_station":
                mid_action = ["prepare", "bread", "true"]
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "get_plate_from_station":
                mid_action = ["prepare", "bread", "true"]
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "pickup_plate":
                mid_action = ["prepare", "bread", "true"]
            elif event_now == "put_bread_onto_plate" and event_last == "pickup_bread":
                mid_action = ["prepare", "bread", "true"]

            # assemble lettuceburger
            elif event_now == "put_bread_onto_plate_with_lettuce" and event_last == "get_bread_from_station":
                mid_action = ["assemble", "lettuceburger"]
            elif event_now == "put_bread_onto_plate_with_lettuce" and event_last == "pickup_bread":
                mid_action = ["assemble", "lettuceburger"]
            elif event_now == "put_bread_onto_plate_with_bread" and event_last == "pickup_lettuce_done":
                mid_action = ["assemble", "lettuceburger"]
            elif (
                event_now in ["plate_lettuce_done", "plate_lettuce_done_from_counter"]
                and event_last == "pickup_bread_in_plate"
            ):
                mid_action = ["assemble", "lettuceburger"]
                agent_holding = "lettuceburger"
            elif event_now in ["plate_lettuce_done", "plate_lettuce_done_from_counter"] and event_last in [
                "plate_bread",
                "plate_bread_from_counter",
            ]:
                mid_action = ["assemble", "lettuceburger"]
                agent_holding = "lettuceburger"
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "plate_lettuce_done":
                mid_action = ["assemble", "lettuceburger"]
                agent_holding = "lettuceburger"
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "pickup_lettuce_in_plate":
                mid_action = ["assemble", "lettuceburger"]
                agent_holding = "lettuceburger"

            # assemble beefburger
            elif event_now == "put_bread_onto_plate_with_beef" and event_last == "get_bread_from_station":
                mid_action = ["assemble", "beefburger"]
            elif event_now == "put_bread_onto_plate_with_beef" and event_last == "pickup_bread":
                mid_action = ["assemble", "beefburger"]
            elif event_now == "plate_beef_done_from_pan" and event_last in ["plate_bread", "plate_bread_from_counter"]:
                mid_action = ["assemble", "beefburger"]
                agent_holding = "beefburger"
            elif event_now == "plate_beef_done_from_pan" and event_last == "pickup_bread_in_plate":
                mid_action = ["assemble", "beefburger"]
                agent_holding = "beefburger"
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "plate_beef_done_from_pan":
                mid_action = ["assemble", "beefburger"]
                agent_holding = "beefburger"

            # assemble beeflettuce
            elif event_now == "plate_beef_done_from_pan" and event_last == "plate_lettuce_done_from_cutboard":
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "plate_beef_done_from_pan" and event_last in [
                "plate_lettuce_done",
                "plate_lettuce_done_from_counter",
            ]:
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "plate_beef_done_from_pan" and event_last == "pickup_lettuce_in_plate":
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "plate_lettuce_done_from_cutboard" and event_last == "plate_beef_done_from_pan":
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "plate_lettuce_done_from_cutboard" and event_last == "pickup_beef_done":
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "plate_lettuce_done" and event_last == "plate_beef_done_from_pan":
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "plate_lettuce_done" and event_last == "pickup_beef_done":
                mid_action = ["assemble", "beeflettuce"]
                agent_holding = "beeflettuce"
            elif event_now == "put_lettuce_onto_plate_with_beef" and event_last == "pickup_lettuce_done":
                mid_action = ["assemble", "beeflettuce"]

            # assemble beeflettuceburger
            # lettuceburger and beef
            elif event_now == "plate_beef_done_from_pan" and event_last == "pickup_lettuceburger":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now == "plate_beef_done" and event_last == "pickup_lettuceburger":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now == "plate_lettuceburger" and event_last == "plate_beef_done_from_pan":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            # beefburger and lettuce
            elif event_now == "plate_lettuce_done_from_cutboard" and event_last == "pickup_beefburger":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now == "plate_lettuce_done" and event_last == "pickup_beefburger":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now == "put_onto_plate_with_beefburger" and event_last == "pickup_lettuce_done":
                mid_action = ["assemble", "beeflettuceburger"]
            elif event_now == "plate_beefburger" and event_last == "pickup_lettuce_in_plate":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            # beeflettuce and burger
            elif event_now == "put_onto_plate_with_beeflettuce" and event_last == "get_bread_from_station":
                mid_action = ["assemble", "beeflettuceburger"]
            elif event_now == "put_onto_plate_with_beeflettuce" and event_last == "pickup_bread":
                mid_action = ["assemble", "beeflettuceburger"]
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "pickup_beeflettuce":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and event_last == "pickup_beeflettuce":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now == "plate_beeflettuce" and event_last == "pickup_bread_in_plate":
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"

            # pass_on
            # lettuce
            elif event_now == "put_onto_center_counter" and event_last == "get_lettuce_from_station":
                mid_action = ["pass_on", "lettuce", "fresh"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_lettuce_fresh":
                mid_action = ["pass_on", "lettuce", "fresh"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_lettuce_done":
                mid_action = ["pass_on", "lettuce", "done"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_lettuce_in_plate":
                mid_action = ["pass_on", "lettuce", "done"]
            elif event_now == "put_onto_center_counter" and event_last in [
                "plate_lettuce_done",
                "plate_lettuce_done_from_counter",
            ]:
                mid_action = ["pass_on", "lettuce", "done"]
            elif event_now == "put_onto_center_counter" and event_last == "plate_lettuce_done_from_cutboard":
                mid_action = ["pass_on", "lettuce", "done"]
            # beef
            elif event_now == "put_onto_center_counter" and event_last == "get_beef_from_station":
                mid_action = ["pass_on", "beef", "fresh"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_beef_fresh":
                mid_action = ["pass_on", "beef", "fresh"]
            elif event_now == "put_onto_center_counter" and event_last == "plate_beef_done_from_pan":
                mid_action = ["pass_on", "beef", "done"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_beef_done":
                mid_action = ["pass_on", "beef", "done"]
            elif event_now == "put_onto_center_counter" and event_last == "plate_beef_overcooked_from_pan":
                mid_action = ["pass_on", "beef", "overcooked"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_beef_overcooked":
                mid_action = ["pass_on", "beef", "overcooked"]
            # bread
            elif event_now == "put_onto_center_counter" and event_last == "get_bread_from_station":
                mid_action = ["pass_on", "bread"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_bread":
                mid_action = ["pass_on", "bread"]
            elif event_now == "put_onto_center_counter" and event_last in ["plate_bread", "plate_bread_from_counter"]:
                mid_action = ["pass_on", "bread"]
            elif event_now == "put_onto_center_counter" and event_last == "pickup_bread_in_plate":
                mid_action = ["pass_on", "bread"]
            # plate
            elif event_now == "put_onto_center_counter" and event_last == "get_plate_from_station":
                mid_action = ["pass_on", "plate"]
            elif event_now == "put_onto_center_counter" and event_last == "pick_up_plate":
                mid_action = ["pass_on", "plate"]
            # fireextinguisher
            elif event_now == "put_onto_center_counter" and event_last == "pickup_fireextinguisher":
                mid_action = ["pass_on", "plate"]
            # beefburger
            elif event_now == "put_onto_center_counter" and event_last == "pick_up_beefburger":
                mid_action = ["pass_on", "beefburger"]
            # lettuceburger
            elif event_now == "put_onto_center_counter" and event_last == "pick_up_lettuceburger":
                mid_action = ["pass_on", "lettuceburger"]
            # beeflettuce
            elif event_now == "put_onto_center_counter" and event_last == "pick_up_beeflettuce":
                mid_action = ["pass_on", "beeflettuce"]
            # beeflettuceburger
            elif event_now == "put_onto_center_counter" and event_last == "pick_up_beeflettuceburger":
                mid_action = ["pass_on", "beeflettuceburger"]

            # serve
            elif event_now == "deliver_burger":
                if event_last == "pickup_lettuceburger":
                    mid_action = ["serve", "lettuceburger"]
                elif event_last == "pickup_beefburger":
                    mid_action = ["serve", "beefburger"]
                elif event_last == "pickup_beeflettuceburger":
                    mid_action = ["serve", "beeflettuceburger"]
                # else:
                #     mid_action = ["serve", "not a food"]

            # clean_a_counter
            elif event_now == "drop_food":
                if "pickup" in event_last:
                    mid_action = ["clean_a_counter"]

            return mid_action

        def _three_step_action(event_now: str, event_last: str, event_last_2: str):
            nonlocal agent_holding
            agent_holding = None
            mid_action = None
            # assemble beeflettuceburger
            # lettuceburger and beef
            if event_now == "plate_beef_done_from_pan" and _two_step_action(event_last, event_last_2) == [
                "assemble",
                "lettuceburger",
            ]:
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now == "plate_beef_done" and _two_step_action(event_last, event_last_2) == [
                "assemble",
                "lettuceburger",
            ]:
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            # beefburger and lettuce
            elif event_now == "plate_lettuce_done_from_cutboard" and _two_step_action(event_last, event_last_2) == [
                "assemble",
                "beefburger",
            ]:
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now in ["plate_lettuce_done", "plate_lettuce_done_from_counter"] and _two_step_action(
                event_last, event_last_2
            ) == [
                "assemble",
                "beefburger",
            ]:
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            # beeflettuce and burger
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and _two_step_action(
                event_last, event_last_2
            ) == [
                "assemble",
                "beeflettuce",
            ]:
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"
            elif event_now in ["plate_bread", "plate_bread_from_counter"] and _two_step_action(
                event_last, event_last_2
            ) == [
                "assemble",
                "beeflettuce",
            ]:
                mid_action = ["assemble", "beeflettuceburger"]
                agent_holding = "beeflettuceburger"

            # pass_on
            elif event_now == "put_onto_center_counter":
                mid_action_last = _two_step_action(event_last, event_last_2)
                if (
                    mid_action_last
                    == [
                        "assemble",
                        "lettuceburger",
                    ]
                    and agent_holding == "lettuceburger"
                ):
                    mid_action = ["pass_on", "lettuceburger"]
                elif (
                    mid_action_last
                    == [
                        "assemble",
                        "beefburger",
                    ]
                    and agent_holding == "beefburger"
                ):
                    mid_action = ["pass_on", "beefburger"]
                elif (
                    mid_action_last
                    == [
                        "assemble",
                        "beeflettuce",
                    ]
                    and agent_holding == "beeflettuce"
                ):
                    mid_action = ["pass_on", "beeflettuce"]
                elif (
                    mid_action_last
                    == [
                        "assemble",
                        "beeflettuceburger",
                    ]
                    and agent_holding == "beeflettuceburger"
                ):
                    mid_action = ["pass_on", "beeflettuceburger"]

            # serve
            elif event_now == "deliver_burger":
                mid_action_last = _two_step_action(event_last, event_last_2)
                if mid_action_last == [
                    "assemble",
                    "lettuceburger",
                ]:
                    mid_action = ["serve", "lettuceburger"]
                elif mid_action_last == [
                    "assemble",
                    "beefburger",
                ]:
                    mid_action = ["serve", "beefburger"]
                elif mid_action_last == [
                    "assemble",
                    "beeflettuceburger",
                ]:
                    mid_action = ["serve", "beeflettuceburger"]
                # else:
                #     mid_action = ["serve", "not a food"]
            return mid_action

        def _four_step_action(event_now: str, event_last: str, event_last_2: str, event_last_3):
            nonlocal agent_holding
            agent_holding = None
            mid_action = None
            # pass_on
            if event_now == "put_onto_center_counter":
                if (
                    _three_step_action(event_last, event_last_2, event_last_3)
                    == [
                        "assemble",
                        "beeflettuceburger",
                    ]
                    and agent_holding == "beeflettuceburger"
                ):
                    mid_action = ["pass_on", "beeflettuceburger"]

            # serve
            elif event_now == "deliver_burger" and _three_step_action(event_last, event_last_2, event_last_3) == [
                "assemble",
                "beeflettuceburger",
            ]:
                mid_action = ["serve", "beeflettuceburger"]
            return mid_action

        mid_action_all = {}
        for agent_id, agent in enumerate(self.agents):
            event_list = agent.event_list
            mid_action_list = []
            for i, event_now in enumerate(event_list):
                event_now = event_list[i]
                event_last = event_list[i - 1] if i > 0 else ""
                event_last2 = event_list[i - 2] if i > 1 else ""
                event_last3 = event_list[i - 3] if i > 2 else ""
                action1 = _one_step_work(event_now)
                action2 = _two_step_action(event_now, event_last)
                action3 = _three_step_action(event_now, event_last, event_last2)
                action4 = _four_step_action(event_now, event_last, event_last2, event_last3)
                if action1 != None:
                    mid_action_list.append(action1)
                if action2 != None and action2 != action1:
                    mid_action_list.append(action2)
                if action3 != None and action3 != action2:
                    mid_action_list.append(action3)
                if action4 != None and action4 != action3:
                    mid_action_list.append(action4)
            mid_action_all[agent_id] = mid_action_list
        return mid_action_all

    def add_object(self, obj):
        self.world_objects[type(obj).__name__].append(obj)

    def delete_object(self, obj):
        self.world_objects[type(obj).__name__].remove(obj)

    def accepts(self, static_object: StaticObject, dynamic_object: DynamicObject) -> bool:
        if static_object.accepts([dynamic_object]) and len(self.get_objects_at(static_object.location)) == 1:
            return True
        return False

    def index_objects(self):
        for type_name, obj_list in self.world_objects.items():
            for abstract_class in ABSTRACT_GAME_CLASSES:
                if issubclass(StringToClass[type_name], abstract_class):
                    self.abstract_index[abstract_class].extend(obj_list)

    def get_object_list(self):
        object_list = []
        for value in self.world_objects.values():
            object_list.extend(value)
        return object_list

    def get_dynamic_object_list(self):
        object_list = []
        for values in self.world_objects.values():
            for value in values:
                if isinstance(value, DynamicObject):
                    object_list.append(value)
        return object_list

    def get_static_object_list(self):
        object_list = []
        for values in self.world_objects.values():
            for value in values:
                if isinstance(value, StaticObject):
                    object_list.append(value)
        return object_list

    def progress_world(self):
        for obj in self.abstract_index[ProgressingObject]:
            if obj.powered:
                dynamic_objects = self.get_objects_at(obj.location, DynamicObject)
                # print(dynamic_objects)
                if len(dynamic_objects) != 0:
                    if dynamic_objects[0].current_progress == dynamic_objects[0].overcooked_progress + 1:
                        # add fire because overcooked
                        fire = Fire(obj.location)
                        self.add_object(fire)

                obj.progress(dynamic_objects)

    def perform_agent_actions(self, agents, actions):
        # for i, action in enumerate(actions):
        #     self.prev_holding[i] = agents[i].holding.__class__.__name__ if agents[i].holding else None

        rewards = np.array([0.0 for _ in agents])
        action_rewards = np.array([0.0 for agent in agents])
        for agent, action in zip(agents, actions):
            if action is None:
                continue
            if 0 < action < 5:
                agent.change_orientation(action)
        cleaned_actions = self.check_inbounds(agents, actions)
        collision_actions = self.check_collisions(agents, cleaned_actions)
        for i, (agent, action) in enumerate(zip(agents, collision_actions)):
            if action is None:
                continue
            reward, action_reward = self.perform_agent_action(agent, action)

            rewards += reward
            action_rewards += action_reward

        self.progress_world()

        # self.perceive_events(actions)
        # self.print_map(self.agents)
        # rewards is part of progress reward for onion soup
        return rewards, action_rewards

    def perform_agent_action(self, agent: Agent, action: int | None):
        reward = 0
        action_reward = 0
        # print("action:", action)
        if action == 0:
            agent.current_event = None
        elif 0 < action < 5:
            self.resolve_walking_action(agent, action)
            agent.current_event = None
        elif action == 5:
            current_event = ""
            additional_event = ""
            interaction_location = self.get_target_location(agent, agent.orientation)
            if any([agent.location == interaction_location for agent in self.agents]):
                return reward, action_reward
            dynamic_objects = self.get_objects_at(interaction_location, DynamicObject)
            static_object = self.get_objects_at(interaction_location, StaticObject)[0]
            # get food from station
            if not agent.holding and not dynamic_objects:
                if isinstance(static_object, Station):
                    food = static_object.get_food()
                    self.add_object(food)
                    agent.grab(food)

                    # Update event list
                    if isinstance(food, Lettuce):
                        current_event = "get_lettuce_from_station"
                    elif isinstance(food, Beef):
                        current_event = "get_beef_from_station"
                    elif isinstance(food, Bread):
                        current_event = "get_bread_from_station"
                    elif isinstance(food, Plate):
                        current_event = "get_plate_from_station"

                    food.agents.append((agent.id, current_event))

            elif agent.holding and not dynamic_objects:
                if static_object.accepts([agent.holding]):
                    # Update event list
                    if isinstance(static_object, SoupPot):
                        static_object.content = agent.holding
                        current_event = "put_onto_pot"
                    elif isinstance(static_object, Pan):
                        static_object.content = agent.holding
                        current_event = "put_onto_pan"
                        agent.holding.agents.append((agent.id, current_event))
                    elif isinstance(static_object, CutBoard):
                        static_object.content = agent.holding
                        current_event = "put_onto_cutboard"
                        if not agent.holding.done():
                            agent.holding.agents.append((agent.id, current_event))
                    elif isinstance(static_object, Counter):
                        if static_object.is_center:
                            current_event = "put_onto_center_counter"
                        else:
                            current_event = "put_onto_counter"
                    elif isinstance(static_object, DeliverSquare):
                        current_event = "deliver_burger"
                        # logger.info("deliver burger!")
                        agent.holding.content[0].agents.append((agent.id, current_event))
                        self.deliver_log.append(
                            [
                                agent.id,
                                ClassToString[agent.holding.content[0].__class__],
                                None,
                                {
                                    ClassToString[agent.holding.content[0].__class__]: agent.holding.content[0].agents
                                    + agent.holding.agents
                                },
                            ]
                        )

                    agent.put_down(interaction_location)

                elif isinstance(static_object, Dustbin):
                    dynamic_objects = self.get_objects_at(agent.location, DynamicObject)
                    # print(dynamic_objects)
                    if not isinstance(agent.holding, FireExtinguisher):
                        if isinstance(agent.holding, Container):
                            agent.holding.remove(self)
                        else:
                            for obj in dynamic_objects:
                                if not isinstance(obj, Container):
                                    # print(obj)
                                    self.delete_object(obj)
                            agent.holding = None

                        current_event = "drop_food"

            elif not agent.holding and dynamic_objects:
                if not isinstance(static_object, ProgressingObject):
                    object_to_grab = self.get_highest_order_object(dynamic_objects)
                    if not isinstance(object_to_grab, Fire):
                        if isinstance(static_object, ActionObject):  # currently, only cutboard
                            action_done = static_object.action(dynamic_objects, agent)

                            # if cannot chop or has been chopped done, grab it
                            if not action_done:
                                agent.grab(object_to_grab)
                                static_object.content = None
                                current_event = "pickup_lettuce_done"
                            else:
                                if object_to_grab.done():
                                    current_event = "chop_lettuce(done)"
                                    object_to_grab.agents.append((agent.id, current_event))
                                else:
                                    current_event = "chop_lettuce(doing)"
                                    object_to_grab.agents.append((agent.id, current_event))

                        else:
                            # grab things
                            agent.grab(object_to_grab)
                            if not isinstance(object_to_grab, Counter):
                                static_object.content = None

                            # perceive event
                            if isinstance(object_to_grab, Plate):
                                if len(object_to_grab.content) == 0:
                                    current_event = "pickup_plate"
                                else:
                                    plate_content = object_to_grab.content[0]
                                    if isinstance(plate_content, Beef):
                                        if plate_content.overcooked():
                                            current_event = "pickup_beef_overcooked"
                                        elif plate_content.done():
                                            current_event = "pickup_beef_done"
                                        else:
                                            current_event = "pickup_beef_fresh"
                                    elif isinstance(plate_content, Lettuce):
                                        current_event = "pickup_lettuce_in_plate"
                                    elif isinstance(plate_content, Bread):
                                        current_event = "pickup_bread_in_plate"
                                    elif isinstance(plate_content, BeefBurger):
                                        current_event = "pickup_beefburger"
                                    elif isinstance(plate_content, LettuceBurger):
                                        current_event = "pickup_lettuceburger"
                                    elif isinstance(plate_content, BeefLettuceBurger):
                                        current_event = "pickup_beeflettuceburger"
                                    elif isinstance(plate_content, BeefLettuce):
                                        current_event = "pickup_beeflettuce"
                            elif isinstance(object_to_grab, Lettuce):
                                if object_to_grab.done():
                                    current_event = "pickup_lettuce_done"
                                else:
                                    current_event = "pickup_lettuce_fresh"
                            elif isinstance(object_to_grab, Beef):
                                current_event = "pickup_beef_fresh"
                            elif isinstance(object_to_grab, Bread):
                                current_event = "pickup_bread"
                            elif isinstance(object_to_grab, FireExtinguisher):
                                current_event = "pickup_fireextinguisher"

                else:
                    if isinstance(static_object.content, BlenderFood):
                        static_object.powered = True
            elif agent.holding and dynamic_objects:
                if isinstance(static_object, Pan) or isinstance(static_object, CutBoard):
                    highest = self.get_highest_order_object(dynamic_objects)
                    if isinstance(agent.holding, Container) and not isinstance(highest, Fire):
                        # perceive event
                        (event_res, additional_event) = self.attempt_merge(
                            agent,
                            dynamic_objects,
                            interaction_location,
                            type="soup",
                            pot=static_object,
                        )
                        current_event = event_res
                    elif isinstance(agent.holding, FireExtinguisher) and isinstance(highest, Fire):
                        # put off fire
                        highest.putoff()
                        current_event = "put_out_fire(doing)"
                        if highest.put_num == 5:
                            self.delete_object(highest)
                            current_event = "put_out_fire(done)"

                elif isinstance(static_object, Counter):
                    # perceive event
                    (event_res, additional_event) = self.attempt_merge(agent, dynamic_objects, interaction_location)
                    current_event = event_res

            # update current event list
            # print(current_event)
            if current_event:
                if len(agent.event_list) > 0:
                    if current_event == "chop_lettuce(doing)":
                        # if agent.event_list[-1] != "chop_lettuce(doing)":
                        #     agent.event_list.append(current_event)
                        # else:
                        #     agent.event_list[-1] = current_event
                        agent.event_list.append(current_event)
                    elif current_event == "put_out_fire(doing)":
                        # if agent.event_list[-1] != "put_out_fire(doing)":
                        #     agent.event_list.append(current_event)
                        # else:
                        #     agent.event_list[-1] = current_event
                        agent.event_list.append(current_event)
                    elif (
                        current_event.startswith("put_onto_plate")
                        or current_event in ["put_bread_onto_plate", "put_lettuce_onto_plate"]
                    ) and additional_event is not None:
                        agent.event_list.append(current_event)
                        agent.event_list.append(additional_event)
                    else:
                        agent.event_list.append(current_event)
                else:
                    agent.event_list.append(current_event)

                agent.current_event = current_event
            else:
                agent.current_event = None

        return reward, action_reward

    def resolve_walking_action(self, agent: Agent, action):
        target_location = self.get_target_location(agent, action)
        if self.square_walkable(target_location):
            agent.move_to(target_location)

    def get_highest_order_object(self, objects: List[DynamicObject]):
        order = [Fire, FireExtinguisher, Container, Food]
        for obj_type in order:
            obj = self.filter_obj(objects, obj_type)
            if obj:
                return obj
        return None

    @staticmethod
    def get_target_location(agent, action):
        if action == 1:
            target_location = (agent.location[0] - 1, agent.location[1])
        elif action == 2:
            target_location = (agent.location[0] + 1, agent.location[1])
        elif action == 3:
            target_location = (agent.location[0], agent.location[1] + 1)
        elif action == 4:
            target_location = (agent.location[0], agent.location[1] - 1)
        else:
            target_location = (agent.location[0], agent.location[1])
        return target_location

    @staticmethod
    def filter_obj(objects: List[DynamicObject], obj_type):
        filtered_objects = [obj for obj in objects if isinstance(obj, obj_type)]
        if len(filtered_objects) > 1:
            # raise Exception(f"Too many {obj_type} in one place!")
            return filtered_objects[0]
        elif len(filtered_objects) == 1:
            return filtered_objects[0]
        else:
            return None

    def check_inbounds(self, agents, actions):
        cleaned_actions = []
        for agent, action in zip(agents, actions):
            if action == 0 or action == 5:
                cleaned_actions.append(action)
                continue
            target_location = self.get_target_location(agent, action)
            if target_location[0] > self.width - 1 or target_location[0] < 0:
                action = 0
            if target_location[1] > self.height - 1 or target_location[1] < 0:
                action = 0
            cleaned_actions.append(action)
        return cleaned_actions

    def check_collisions(self, agents, actions):
        collision_actions = []
        target_locations = []
        walkable = []
        current_pos = [agent.location for agent in agents]
        for agent, action in zip(agents, actions):
            target_location = self.get_target_location(agent, action)
            target_walkable = self.square_walkable(target_location)
            end_location = target_location if target_walkable else agent.location
            target_locations.append(end_location)
            walkable.append(target_walkable)
        for idx, (action, target_location, target_walkable) in enumerate(zip(actions, target_locations, walkable)):
            # if target_location in target_locations[:idx] + target_locations[idx+1:] and target_walkable:
            if (
                action != 5
                and target_location in target_locations[:idx] + current_pos[:idx] + current_pos[idx + 1 :]
                and target_walkable
            ):
                collision_actions.append(0)
            else:
                collision_actions.append(action)
        return collision_actions

    def square_walkable(self, location):
        objects = self.get_objects_at(location, StaticObject)
        if len(objects) != 1:
            raise Exception(f"Not exactly one static object at location: {location}")
        return objects[0].walkable

    def get_abstract_object_at(self, location, object_type):
        return [obj for obj in self.abstract_index[object_type] if obj.location == location]

    def get_objects_at(self, location, object_type=object):
        # print(location)
        located_objects = []
        # print(self.world_objects.items())
        for obj_class_string, objects in self.world_objects.items():
            # print(objects)
            # if obj_class_string == "SoupPot":
            #     print(objects)
            # print(obj_class_string)
            obj_class = StringToClass[obj_class_string]
            # print(obj_class, object_type, issubclass(obj_class, object_type))
            # if obj_class_string == "Counter":
            #     print(obj_class == Counter, issubclass(obj_class, Counter))
            # if object_type == Counter:
            #     print(obj_class_string)
            if not issubclass(obj_class, object_type):
                continue
            for obj in objects:
                # print(obj.location, location)
                if obj.location == location:
                    located_objects.append(obj)
                    # if object_type == Counter:
                    #     print(obj.location, located_objects, obj_class_string)
        return located_objects

    def attempt_merge(
        self,
        agent: Agent,
        dynamic_objects: List[DynamicObject],
        target_location,
        type=None,
        pot=None,
    ):
        def get_plate_event(highest):
            event = ""
            if isinstance(highest, Beef):
                if highest.overcooked():
                    event = "plate_beef_overcooked"
                elif highest.done():
                    event = "plate_beef_done"

            elif isinstance(highest, Lettuce):
                event = "plate_lettuce_done"
            elif isinstance(highest, Bread):
                event = "plate_bread"
            elif isinstance(highest, BeefBurger):
                event = "plate_beefburger"
            elif isinstance(highest, LettuceBurger):
                event = "plate_lettuceburger"
            elif isinstance(highest, BeefLettuce):
                event = "plate_beeflettuce"
            elif isinstance(highest, BeefLettuceBurger):
                event = "plate_beeflettuceburger"
            return event

        additional_event = ""
        target = dynamic_objects[0]
        event = ""
        if type == "soup":
            # has been cooked
            if target.done() or (isinstance(target, Beef) and target.overcooked()):
                if len(agent.holding.content) == 0:
                    # agent.holding.player.append(agent.name)
                    if isinstance(target, Beef):
                        if target.overcooked():
                            event = "plate_beef_overcooked_from_pan"
                        elif target.done():
                            event = "plate_beef_done_from_pan"
                            target.agents.append((agent.id, event))
                    elif isinstance(target, Lettuce):
                        event = "plate_lettuce_done_from_cutboard"
                        target.agents.append((agent.id, event))
                    pot.content = None
                    agent.holding.add_content(target)
                    target.move_to(agent.location)
                elif len(agent.holding.content) == 1:
                    if is_food_mixable(agent.holding.content[0], target):
                        if isinstance(target, Beef):
                            if target.overcooked():
                                event = "plate_beef_overcooked_from_pan"
                            elif target.done():
                                event = "plate_beef_done_from_pan"
                                target.agents.append((agent.id, event))
                        elif isinstance(target, Lettuce):
                            event = "plate_lettuce_done_from_cutboard"
                            target.agents.append((agent.id, event))
                        pot.content = None
                        new_obj = agent.holding.content[0].mix(target)
                        self.add_object(new_obj)
                        self.delete_object(agent.holding.content[0])
                        self.delete_object(target)
                        agent.holding.content = [new_obj]
            return event, additional_event

        highest = self.get_highest_order_object(dynamic_objects)
        if isinstance(agent.holding, Food) and isinstance(highest, Food):
            # mixed in pot, not be used yet.
            if is_food_mixable(agent.holding, target):
                if pot:
                    new_obj = highest.mix(agent.holding)
                    self.add_object(new_obj)
                    self.delete_object(agent.holding)
                    self.delete_object(target)
                    agent.holding = None
                    pot.content = new_obj

        elif isinstance(agent.holding, Food) and isinstance(highest, Container):
            # put_onto_plate
            new_obj = None
            if len(highest.content) == 0:
                if (not isinstance(agent.holding, Lettuce) or agent.holding.done()) and (
                    not isinstance(agent.holding, Beef) or agent.holding.done() or agent.holding.overcooked()
                ):
                    highest.content = [agent.holding]
                    new_obj = agent.holding
                    agent.holding.move_to(highest.location)
                    agent.holding = None
                    if isinstance(new_obj, Lettuce):
                        event = "put_lettuce_onto_plate"
                        new_obj.agents.append((agent.id, event))
                    elif isinstance(new_obj, Bread):
                        event = "put_bread_onto_plate"
                        new_obj.agents.append((agent.id, event))
                    else:
                        event = "put_onto_plate"
                        logger.warning(f"Unrecognized object {new_obj}")
            elif is_food_mixable(agent.holding, highest.content[0]):
                if isinstance(highest.content[0], Beef):
                    if isinstance(agent.holding, Lettuce):
                        event = "put_lettuce_onto_plate_with_beef"
                    elif isinstance(agent.holding, Bread):
                        event = "put_bread_onto_plate_with_beef"
                    else:
                        logger.warning(f"Unrecognized object {agent.holding}")
                        event = "put_onto_plate_with_beef"
                elif isinstance(highest.content[0], Lettuce):
                    event = "put_onto_plate_with_lettuce"
                elif isinstance(highest.content[0], Bread):
                    event = "put_onto_plate_with_bread"
                elif isinstance(highest.content[0], BeefBurger):
                    event = "put_onto_plate_with_beefburger"
                # elif isinstance(highest.content[0], LettuceBurger):
                #     event = "put_onto_plate_with_lettuceburger"
                elif isinstance(highest.content[0], BeefLettuce):
                    event = "put_onto_plate_with_beeflettuce"
                agent.holding.agents.append((agent.id, event))
                new_obj = highest.content[0].mix(agent.holding)
                self.add_object(new_obj)
                self.delete_object(agent.holding)
                self.delete_object(highest.content[0])
                highest.content = [new_obj]
                agent.holding = None

            if event.startswith("put_onto_plate") or event in ["put_bread_onto_plate", "put_lettuce_onto_plate"]:
                counter_here = self.get_objects_at(highest.location, Counter)
                if counter_here != [] and counter_here[0].is_center:
                    additional_event = str("pass_on_" + new_obj.name().lower())
                    if isinstance(new_obj, Lettuce) or isinstance(new_obj, Beef):
                        if new_obj.fresh():
                            additional_event += "_fresh"
                        elif new_obj.done():
                            additional_event += "_done"
                        elif isinstance(new_obj, Beef) and new_obj.overcooked():
                            additional_event += "_overcooked"
                # print(highest.content)
        elif isinstance(agent.holding, Container) and isinstance(highest, Food):
            # plate
            if len(agent.holding.content) == 0:
                if (not isinstance(highest, Lettuce) or highest.done()) and (
                    not isinstance(highest, Beef) or highest.done() or highest.overcooked()
                ):
                    # perceive event
                    event = get_plate_event(highest)
                    if isinstance(highest, (Lettuce, Bread)):
                        event = f"{event}_from_counter"
                        highest.agents.append((agent.id, event))
                    agent.holding.content = [highest]
                    highest.move_to(agent.location)
            elif is_food_mixable(agent.holding.content[0], highest):
                # perceive event
                event = get_plate_event(highest)
                if isinstance(highest, (Lettuce, Bread)):
                    event = f"{event}_from_counter"
                    highest.agents.append((agent.id, event))
                new_obj = agent.holding.content[0].mix(highest)
                self.add_object(new_obj)
                self.delete_object(agent.holding.content[0])
                self.delete_object(highest)
                agent.holding.content = [new_obj]

        elif isinstance(agent.holding, Container) and isinstance(highest, Container):
            # plate to plate
            if len(agent.holding.content) == 0 and len(highest.content) > 0:
                # perceive event
                event = get_plate_event(highest.content[0])
                agent.holding.content = highest.content
                agent.holding.content[0].move_to(agent.location)
                highest.content = []
            elif (
                len(agent.holding.content) > 0
                and len(highest.content) > 0
                and is_food_mixable(agent.holding.content[0], highest.content[0])
            ):
                # perceive event
                event = get_plate_event(highest.content[0])
                new_obj = agent.holding.content[0].mix(highest.content[0])
                self.add_object(new_obj)
                self.delete_object(agent.holding.content[0])
                self.delete_object(highest.content[0])
                agent.holding.content = [new_obj]
                highest.content = []

        return event, additional_event

    def load_new_style_level(self, level_name, num_agents):
        my_path = os.path.realpath(__file__)
        dir_name = os.path.dirname(my_path)
        path = Path(dir_name)
        parent = path.parent / f"utils/new_style_level/{level_name}.json"
        with open(parent) as json_file:
            level_object = json.load(json_file)
            json_file.close()
        # self.level_array = level_string_to_level[level_name]
        self.parse_level_layout(level_object)
        self.parse_static_objects(level_object)
        self.parse_dynamic_objects(level_object)
        self.parse_agents(level_object, num_agents)

    def parse_level_layout(self, level_object):
        level_layout = level_object["LEVEL_LAYOUT"]
        x = 0
        y = 0
        for y, line in enumerate(iter(level_layout.splitlines())):
            for x, char in enumerate(line):
                if char == "-":
                    counter = Counter(location=(x, y), is_center=False)
                    self.add_object(counter)
                    self.level_array[y].append(1)
                elif char == "+":
                    counter = Counter(location=(x, y), is_center=True)
                    self.add_object(counter)
                    self.level_array[y].append(1)
                else:
                    floor = Floor(location=(x, y))
                    self.add_object(floor)
                    self.level_array[y].append(0)
            self.level_array.append(list())
        self.level_array = np.transpose(self.level_array[:-1])
        self.level_array = np.array(self.level_array)
        self.width = x + 1
        self.height = y + 1

    def parse_static_objects(self, level_object):
        static_objects = level_object["STATIC_OBJECTS"]
        for static_object in static_objects:
            name = list(static_object.keys())[0]
            for idx in range(static_object[name]["COUNT"]):
                time_out = 0
                while True:
                    # sample a valid position
                    x = random.sample(static_object[name]["X_POSITION"], 1)[0]
                    y = random.sample(static_object[name]["Y_POSITION"], 1)[0]
                    if x < 0 or y < 0 or x > self.width or y > self.height:
                        raise ValueError(f"Position {x} {y} of object {name} is out of bounds set by the level layout!")
                    static_objects_loc = self.get_objects_at((x, y), StaticObject)

                    counter = [obj for obj in static_objects_loc if isinstance(obj, (Counter, Floor))]
                    if counter:
                        if len(counter) != 1:
                            raise ValueError("Too many counter in one place detected during initialization")
                        self.delete_object(counter[0])
                        obj = StringToClass[name](location=(x, y))
                        self.add_object(obj)
                        break
                    else:
                        time_out += 1
                        if time_out > 100:
                            raise ValueError(
                                f"Can't find valid position for object: " f"{static_object} in {time_out} steps"
                            )
                        continue

    def parse_dynamic_objects(self, level_object):
        dynamic_objects = level_object["DYNAMIC_OBJECTS"]
        for dynamic_object in dynamic_objects:
            name = list(dynamic_object.keys())[0]
            for idx in range(dynamic_object[name]["COUNT"]):
                time_out = 0
                while True:
                    x = random.sample(dynamic_object[name]["X_POSITION"], 1)[0]
                    y = random.sample(dynamic_object[name]["Y_POSITION"], 1)[0]
                    if x < 0 or y < 0 or x > self.width or y > self.height:
                        raise ValueError(f"Position {x} {y} of object {name} is out of bounds set by the level layout!")
                    static_objects_loc = self.get_objects_at((x, y), Counter)
                    dynamic_objects_loc = self.get_objects_at((x, y), DynamicObject)

                    if len(static_objects_loc) == 1 and not dynamic_objects_loc:
                        obj = StringToClass[name](location=(x, y))
                        self.add_object(obj)
                        break
                    else:
                        time_out += 1
                        if time_out > 100:
                            raise ValueError(
                                f"Can't find valid position for object: " f"{dynamic_object} in {time_out} steps"
                            )
                        continue

    def parse_agents(self, level_object, num_agents):
        agent_objects = level_object["AGENTS"]
        agent_idx = 0
        for agent_object in agent_objects:
            for idx in range(agent_object["MAX_COUNT"]):
                agent_idx += 1
                if agent_idx > num_agents:
                    return
                time_out = 0
                while True:
                    x = random.sample(agent_object["X_POSITION"], 1)[0]
                    y = random.sample(agent_object["Y_POSITION"], 1)[0]
                    if x < 0 or y < 0 or x > self.width or y > self.height:
                        raise ValueError(f"Position {x} {y} of agent is out of bounds set by the level layout!")
                    static_objects_loc = self.get_objects_at((x, y), Floor)
                    if not any([(x, y) == agent.location for agent in self.agents]) and static_objects_loc:
                        agent = Agent(
                            (int(x), int(y)),
                            self.COLORS[len(self.agents)],
                            "agent-" + str(len(self.agents) + 1),
                            len(self.agents),
                        )
                        self.agents.append(agent)
                        break
                    else:
                        time_out += 1
                        if time_out > 100:
                            raise ValueError(f"Can't find valid position for agent: {agent_object} in {time_out} steps")

    # clear the DeliverSquare when a recipe finished
    def clear_deliver(self, root_loc):
        delivers = self.world_objects["DeliverSquare"]
        players = []
        final_players = []
        wrong_objects = []
        if root_loc is None:
            root_loc = [d.location for d in delivers]
        for deliver in delivers:
            location = deliver.location
            if location in root_loc:
                objects = self.get_objects_at(location, DynamicObject)
                if len(objects) > 0:
                    for obj in objects:
                        self.delete_object(obj)
                        if isinstance(obj, Food):
                            wrong_objects.append(ClassToString[obj.__class__])

        return players, final_players, wrong_objects

    def load_level(self, level, num_agents):
        self.load_new_style_level(level, num_agents)
        self.index_objects()

    def _get_object_desc(self, obj: Object) -> Dict:
        """
        get the object name, status, description
        """
        if isinstance(obj, Lettuce):
            if obj.done():
                return {"name": "Lettuce", "status": "Chopped"}
            else:
                return {"name": "Lettuce", "status": "Unchopped"}
        elif isinstance(obj, Beef):
            if obj.overcooked():
                return {"name": "Beef", "status": "Overcooked"}
            elif obj.done():
                return {"name": "Beef", "status": "Well-cooked"}
            elif obj.in_progress():
                return {"name": "Beef", "status": "In-progress"}
            else:
                return {"name": "Beef", "status": "Fresh"}
        elif isinstance(obj, Plate):
            return {"name": "Plate", "status": "Empty"}
        else:
            return {"name": ClassToString[obj.__class__], "status": ""}

    def get_json_state_simple(self, agent_index):
        json_state = {
            "objects": {
                ("Beef", "Fresh"): 0,
                ("Beef", "In-progress"): 0,
                ("Beef", "Well-cooked"): 0,
                ("Beef", "Overcooked"): 0,
                ("Lettuce", "Unchopped"): 0,
                ("Lettuce", "Chopped"): 0,
                ("Bread", ""): 0,
                ("BeefLettuce", ""): 0,
                ("BeefBurger", ""): 0,
                ("LettuceBurger", ""): 0,
                ("BeefLettuceBurger", ""): 0,
                ("Plate", "Empty"): 0,
                ("FireExtinguisher", ""): 0,
                ("Fire", ""): 0,
            },
            "counters": {
                "Empty": 0,
            },
            "inventory_other_player": {},
        }
        dynamic_objects = self.get_dynamic_object_list()
        # dynamic_objects = [obj for obj in dynamic_objects if isinstance(obj, DynamicObject)]

        static_objects = self.get_static_object_list()
        for s_obj in static_objects:
            if isinstance(s_obj, Counter):
                if len(self.get_objects_at(s_obj.location)) == 1:
                    json_state["counters"]["Empty"] += 1

        other_agents = self.agents[:agent_index] + self.agents[agent_index + 1 :]
        other_agent_idxs = list(range(0, agent_index)) + list(range(agent_index + 1, len(self.agents)))
        other_agent_locations = [agent.location for agent in other_agents]

        for agent_idx, agent in zip(other_agent_idxs, other_agents):
            if agent.holding:
                if isinstance(agent.holding, Plate) and len(agent.holding.content) > 0:
                    obj_desc = self._get_object_desc(agent.holding.content[0])
                else:
                    obj_desc = self._get_object_desc(agent.holding)
            else:
                obj_desc = None
            json_state["inventory_other_player"][agent_idx] = obj_desc

        for obj in dynamic_objects:
            if obj.location in other_agent_locations:
                continue  # can not access
            if isinstance(obj, Plate) and len(obj.content) > 0:
                continue  # avoid duplicate counting
            obj_dict = self._get_object_desc(obj)
            json_state["objects"][(obj_dict["name"], obj_dict["status"])] += 1

        json_state["deliver_log"] = self.deliver_log.copy()
        json_state["total_score"] = self.total_score

        self.deliver_log = []

        return json_state

    def get_json_state(self, agent_index):
        middle = (self.width / 2, self.height / 2)

        json_state = {
            "player_state": {"player0": {}, "player1": {}},
            "objects_state": {
                "Plate": [],
                "Lettuce": [],
                "Beef": [],
                "Bread": [],
                "CutBoard": [],
                "Pan": [],
            },
        }
        agent_locations = []
        for i, agent in enumerate(self.agents):
            pos = agent.location
            agent_locations.append(pos)
            if i == agent_index:
                json_state["player_state"][f"player{i}"]["controlled_by"] = "You"
            else:
                json_state["player_state"][f"player{i}"]["controlled_by"] = "Partner"
            if pos[0] < middle[0] and pos[1] < middle[1]:
                json_state["player_state"][f"player{i}"]["location"] = "Top Left"
            elif pos[0] < middle[0] and pos[1] > middle[1]:
                json_state["player_state"][f"player{i}"]["location"] = "Bottom Left"
            elif pos[0] > middle[0] and pos[1] < middle[1]:
                json_state["player_state"][f"player{i}"]["location"] = "Top Right"
            else:
                json_state["player_state"][f"player{i}"]["location"] = "Bottom Right"
            if agent.holding is None:
                json_state["player_state"][f"player{i}"]["in_hands"] = None
            elif isinstance(agent.holding, Container):
                if len(agent.holding.content) == 0:
                    json_state["player_state"][f"player{i}"]["in_hands"] = self._get_object_desc(agent.holding)
                else:
                    content = self._get_object_desc(agent.holding.content[0])
                    json_state["player_state"][f"player{i}"]["in_hands"] = content
                    # json_state["player_state"][f"player{i}"][
                    #     "in_hands"
                    # ] = f"Plate <with {ClassToString[agent.holding.content[0].__class__]}>"
            else:
                # if isinstance(agent.holding, Lettuce):
                #     if agent.holding.chop_num == agent.holding.max_chop_num:
                #         json_state["player_state"][f"player{i}"]["in_hands"] = "Lettuce <Chopped>"
                #     else:
                #         json_state["player_state"][f"player{i}"]["in_hands"] = "Lettuce <Unchopped>"
                # else:
                #     json_state["player_state"][f"player{i}"]["in_hands"] = f"{ClassToString[agent.holding.__class__]}"
                json_state["player_state"][f"player{i}"]["in_hands"] = self._get_object_desc(agent.holding)
            # agent_str = f"Agent {agent.name} at {agent.location} with orientation {agent.orientation} holding {agent.holding}"
            # print(agent_str)

        for item in self.world_objects["Plate"]:
            pos = item.location
            state_dict = {"location": "", "content": "None"}

            if len(item.content) > 0:
                # state_dict["content"] = ClassToString[item.content[0].__class__]
                state_dict["content"] = self._get_object_desc(item.content[0])
            if pos == agent_locations[0]:
                state_dict["location"] = "in_player0_hand"
            elif pos == agent_locations[1]:
                state_dict["location"] = "in_player1_hand"
            else:
                state_dict["location"] = "on_counter"
            json_state["objects_state"]["Plate"].append(state_dict)

        for item in self.world_objects["Lettuce"]:
            pos = item.location
            state_dict = {"location": "", "status": ""}
            # if item.chop_num == item.max_chop_num:
            # if item.done():
            #     state_dict["status"] = "Chopped"
            # else:
            #     state_dict["status"] = "Unchopped"
            state_dict["status"] = self._get_object_desc(item)["status"]
            if pos == agent_locations[0]:
                state_dict["location"] = "in_player0_hand"
            elif pos == agent_locations[1]:
                state_dict["location"] = "in_player1_hand"
            else:
                cutboard = self.get_objects_at(pos, CutBoard)
                if len(cutboard) > 0:
                    state_dict["location"] = "on_cutboard"
                else:
                    state_dict["location"] = "on_counter"
            json_state["objects_state"]["Lettuce"].append(state_dict)

        for item in self.world_objects["Beef"]:
            pos = item.location
            state_dict = {"location": "", "status": ""}
            # state_dict["status"] = item.blend_state.value
            state_dict["status"] = self._get_object_desc(item)["status"]
            if pos == agent_locations[0]:
                state_dict["location"] = "in_player0_hand"
            elif pos == agent_locations[1]:
                state_dict["location"] = "in_player1_hand"
            else:
                pan = self.get_objects_at(pos, Pan)
                if len(pan) > 0:
                    state_dict["location"] = "in_pan"
                else:
                    state_dict["location"] = "on_counter"
            json_state["objects_state"]["Beef"].append(state_dict)

        for item in self.world_objects["Bread"]:
            pos = item.location
            state_dict = {"location": ""}
            if pos == agent_locations[0]:
                state_dict["location"] = "in_player0_hand"
            elif pos == agent_locations[1]:
                state_dict["location"] = "in_player1_hand"
            else:
                state_dict["location"] = "on_counter"
            json_state["objects_state"]["Bread"].append(state_dict)

        # Pot state
        for item in self.world_objects["Pan"]:
            pos = item.location
            state_dict = {"status": "", "content": ""}
            if item.content is None:
                state_dict["status"] = "empty"
                state_dict["content"] = "None"
            else:
                state_dict["status"] = "full"
                # state_dict["content"] = "Beef <" + item.content.blend_state.value + ">"
                state_dict["content"] = self._get_object_desc(item.content)
                fire = self.get_objects_at(pos, Fire)
                if len(fire) > 0:
                    # fire_str = f"Pot{i} has fire on it, you need to put_out_fire!!"
                    state_dict["status"] = "in_fire"
            json_state["objects_state"]["Pan"].append(state_dict)

        # Fire
        # print(str_state)
        for item in self.world_objects["CutBoard"]:
            pos = item.location
            state_dict = {"status": "", "content": ""}
            lettuce = self.get_objects_at(pos, Lettuce)
            if len(lettuce) == 0:
                state_dict["status"] = "empty"
                state_dict["content"] = "None"
            else:
                state_dict["status"] = "full"
                # if lettuce[0].chop_num == lettuce[0].max_chop_num:
                #     state_dict["content"] = "Lettuce <Chopped>"
                # else:
                #     state_dict["content"] = "Lettuce <Unchopped>"
                state_dict["content"] = self._get_object_desc(lettuce[0])
            json_state["objects_state"]["CutBoard"].append(state_dict)

        return json_state

    # def get_format_state(self):

    #     for i, agent in enumerate

    def get_str_state(self, agent_index):
        middle = (self.width / 2, self.height / 2)

        str_state = []

        for i, agent in enumerate(self.agents):
            pos = agent.location
            if pos[0] < middle[0] and pos[1] < middle[1]:
                str_pos = "Top Left"
            elif pos[0] < middle[0] and pos[1] > middle[1]:
                str_pos = "Bottom Left"
            elif pos[0] > middle[0] and pos[1] < middle[1]:
                str_pos = "Top Right"
            else:
                str_pos = "Bottom Right"
            if i == agent_index:
                if agent.holding is None:
                    str_state.append(f"You are at the {str_pos} of the map, holding nothing")
                elif isinstance(agent.holding, Container):
                    if len(agent.holding.content) == 0:
                        str_state.append(
                            f"You are at the {str_pos} of the map, holding empty {ClassToString[agent.holding.__class__]}"
                        )
                    else:
                        str_state.append(
                            f"You are at the {str_pos} of the map, holding {ClassToString[agent.holding.__class__]} with {ClassToString[agent.holding.content[0].__class__]} in it"
                        )
                else:
                    if isinstance(agent.holding, Lettuce):
                        if agent.holding.chop_num == agent.holding.max_chop_num:
                            str_state.append(
                                f"You are at the {str_pos} of the map, holding chopped {ClassToString[agent.holding.__class__]}"
                            )
                        else:
                            str_state.append(
                                f"You are at the {str_pos} of the map, holding unchopped {ClassToString[agent.holding.__class__]}"
                            )
                    else:
                        str_state.append(
                            f"You are at the {str_pos} of the map, holding {ClassToString[agent.holding.__class__]}"
                        )
            else:
                if agent.holding is None:
                    str_state.append(f"Your partner is at the {str_pos} of the map, holding nothing")
                elif isinstance(agent.holding, Container):
                    if len(agent.holding.content) == 0:
                        str_state.append(
                            f"You are at the {str_pos} of the map, holding empty {ClassToString[agent.holding.__class__]}"
                        )
                    else:
                        str_state.append(
                            f"You are at the {str_pos} of the map, holding {ClassToString[agent.holding.__class__]} with {ClassToString[agent.holding.content[0].__class__]} in it"
                        )
                else:
                    if isinstance(agent.holding, Lettuce):
                        if agent.holding.chop_num == agent.holding.max_chop_num:
                            str_state.append(
                                f"Your partner is at the {str_pos} of the map, holding chopped {ClassToString[agent.holding.__class__]}"
                            )
                        else:
                            str_state.append(
                                f"Your partner is at the {str_pos} of the map, holding unchopped {ClassToString[agent.holding.__class__]}"
                            )
                    else:
                        str_state.append(
                            f"Your partner is at the {str_pos} of the map, holding {ClassToString[agent.holding.__class__]}"
                        )
            # agent_str = f"Agent {agent.name} at {agent.location} with orientation {agent.orientation} holding {agent.holding}"
            # print(agent_str)

        # Pot state
        for i, pot in enumerate(self.world_objects["Pan"]):
            if pot.content is not None:
                pot_str = f"Pot{i} has {pot.content.blend_state.value} {ClassToString[pot.content.__class__]} in it"
                # print(pot_str)
                str_state.append(pot_str)
                fire = self.get_objects_at(pot.location, Fire)
                if len(fire) > 0:
                    fire_str = f"Pot{i} has fire on it, you need to put_out_fire!!"
                    str_state.append(fire_str)
        # Fire
        # print(str_state)
        for i, cutboard in enumerate(self.world_objects["CutBoard"]):
            pos = cutboard.location
            lettuce = self.get_objects_at(pos, Lettuce)
            if len(lettuce) > 0:
                if lettuce[0].chop_num == lettuce[0].max_chop_num:
                    lettuce_str = f"Cutboard{i} has chopped {ClassToString[lettuce[0].__class__]} on it"
                else:
                    lettuce_str = f"Cutboard{i} has unchopped {ClassToString[lettuce[0].__class__]} on it"
                # print(lettuce_str)
                str_state.append(lettuce_str)
        # cutboard_objects = []
        other_objects = []

        for y in range(self.height):
            for x in range(self.width):
                location = (x, y)
                # print(location)
                counter = self.get_objects_at(location, Counter)
                # cutboard = self.get_objects_at(location, CutBoard)
                # print(counter)
                if len(counter) > 0:
                    objs = self.get_objects_at(location)
                    plate = []
                    food = []
                    human = False
                    for obj in objs:
                        if isinstance(obj, Food):
                            food.append(obj)
                        if isinstance(obj, Plate):
                            plate.append(obj)
                        if isinstance(obj, Agent):
                            human = True
                    if human:
                        continue
                    if len(plate) == 1:
                        if len(plate[0].content) > 0:
                            if "Beef" == ClassToString[plate[0].content[0].__class__]:
                                state_beef = plate[0].content[0].blend_state.value
                                # print(f"state_beef is {state_beef}")
                                ot_str = (
                                    f"Plate with content {state_beef} {ClassToString[plate[0].content[0].__class__]}"
                                )
                            else:
                                ot_str = f"Plate with content {ClassToString[plate[0].content[0].__class__]}"
                            other_objects.append(ot_str)
                        else:
                            ot_str = f"Empty Plate"
                            other_objects.append(ot_str)
                    elif len(food) == 1:
                        ot_str = f"{ClassToString[food[0].__class__]}"
                        other_objects.append(ot_str)

        if len(other_objects) > 0:
            str_state.append("Objects on Counter:")
            for obj in other_objects:
                str_state.append(obj)
        # print(str_state)
        return ", ".join(str_state)

    def get_current_event(self, agents):
        current_event = []
        for i, agent in enumerate(agents):
            current_event.append(agent.current_event)
        return current_event

    def print_map(self, agents, show=True):
        column_width = 7
        output = ""
        agent_states = {}
        for i, agent in enumerate(agents):
            agent_states.update({agent.location: (agent.orientation, i)})
        for y in range(self.height):
            for x in range(self.width):
                location = (x, y)
                out = ""
                if location in agent_states.keys():
                    out += ACTION2LABEL[agent_states[location][0]]
                    out += str(agent_states[location][1])
                objs = self.get_objects_at(location)
                for obj in objs:
                    objtype = type(obj)
                    if objtype == Floor:
                        continue
                    if objtype in OBJ2LABEL.keys():
                        out += OBJ2LABEL[objtype]
                    elif objtype in CHOPFOOD2LABEL.keys():
                        out += CHOPFOOD2LABEL[objtype][obj.done()]
                    elif objtype in BLENDERFOOD2LABEL.keys():
                        out += (
                            BLENDERFOOD2LABEL[objtype]["overcooked"]
                            if obj.overcooked()
                            else BLENDERFOOD2LABEL[objtype][obj.done()]
                        )
                    else:
                        print("-" * os.get_terminal_size().columns)
                        print("Class " + ClassToString[objtype] + " have no label")
                        print("-" * os.get_terminal_size().columns)
                output += out.ljust(column_width)
            if y != self.height - 1:
                output += "\n\n"
        if show:
            print(output)
        return output
