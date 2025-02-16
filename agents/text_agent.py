import random
from collections import Counter as Cnter
from copy import deepcopy
from typing import Callable, List, Tuple

from gym_cooking.cooking_world.cooking_world import (
    CookingWorld,
    is_food_mixable,
    is_mixable,
)
from gym_cooking.cooking_world.world_objects import *

from utils.astar import *

TEXT_ACTION_SUCCESS = -1
TEXT_ACTION_FAILURE = -2

COLORS = ["blue", "magenta", "red", "green"]

ORIENTATION_TO_SHIFT = {
    1: (-1, 0),  # left
    2: (1, 0),  # right
    3: (0, 1),  # down
    4: (0, -1),  # up
}


def get_neighbor_position(position: Tuple[int, int]):
    (x, y) = position
    return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


class TextAgent:
    legal_text_actions = [
        # Get ingredients from station
        "get_plate_from_station",
        "get_lettuce_from_station",
        "get_beef_from_station",
        "get_bread_from_station",
        # Pickup from counter (even within a plate) with nothing in hand, the agent will put in-hand things onto the counter
        "pickup_plate",
        "pickup_lettuce_fresh",
        "pickup_lettuce_done",
        "pickup_lettuce_in_plate",
        "pickup_beef_fresh",
        "pickup_beef_done",
        "pickup_beef_overcooked",
        "pickup_bread",
        "pickup_bread_in_plate",
        "pickup_beeflettuce",
        "pickup_lettuceburger",
        "pickup_beefburger",
        "pickup_beeflettuceburger",
        "pickup_fireextinguisher",
        # Put in-hand ingredients (even within a plate) onto containers or static objects, after which the agent holds nothing
        "put_onto_cutboard",
        "put_onto_pan",
        "put_onto_counter",
        "put_onto_center_counter",
        "put_onto_edge_counter",
        "put_onto_plate",
        "put_onto_plate_with_beef",
        "put_onto_plate_with_bread",
        "put_onto_plate_with_lettuce",
        "put_onto_plate_with_beeflettuce",
        "put_onto_plate_with_beefburger",
        # "put_onto_plate_with_lettuceburger",
        # Pickup ingredients using a plate (in which may be other ingredients) from a static object (beef and lettuce) or from counter, for the targeted ingredient .done() shuold be True or .overcooked() should be True
        "plate_beef_done",
        "plate_beef_done_from_pan",
        "plate_beef_overcooked",
        "plate_beef_overcooked_from_pan",
        "plate_lettuce_done",
        "plate_lettuce_done_from_counter",  # for event count
        "plate_lettuce_done_from_cutboard",
        "plate_bread",
        "plate_bread_from_counter",  # for event count
        "plate_beeflettuce",
        "plate_lettuceburger",
        "plate_beefburger",
        # Others
        "chop_lettuce",
        "put_out_fire",
        "drop_food",
        "deliver",
        "wait",
    ]
    legal_get_targets: List[Tuple[str, str]] = [
        ("PlateStation", ""),
        ("LettuceStation", ""),
        ("BeefStation", ""),
        ("BreadStation", ""),
    ]
    legal_pickup_targets: List[Tuple[str, str]] = [
        ("Plate", ""),
        ("Lettuce", "fresh"),
        ("Lettuce", "done"),
        ("Lettuce", "in_plate"),
        ("Beef", "fresh"),
        ("Beef", "done"),
        ("Beef", "overcooked"),
        ("Bread", ""),
        ("Bread", "in_plate"),
        ("BeefLettuce", ""),
        ("LettuceBurger", ""),
        ("BeefBurger", ""),
        ("BeefLettuceBurger", ""),
        ("FireExtinguisher", ""),
    ]
    legal_put_onto_targets: List[Tuple[str, str]] = [
        ("CutBoard", ""),
        # ("CenterCounter", ""),
        # ("EdgeCounter", ""),
        ("Pan", ""),
        ("Counter", ""),
        ("Counter", "center"),
        ("Counter", "edge"),
        ("Plate", ""),
        ("Beef", "done"),
        ("Bread", ""),
        ("Lettuce", "done"),
        ("BeefLettuce", ""),
        ("BeefBurger", ""),
        ("LettuceBurger", ""),
    ]
    legal_plate_targets: List[Tuple[str, str]] = [
        ("Beef", "done"),
        ("Beef", "overcooked"),
        ("Lettuce", "done"),
        # the second item is the target_status of self.plate_target
        ("Pan", "done"),
        ("Pan", "overcooked"),
        ("CutBoard", "done"),
        ("Bread", ""),
        ("BeefLettuce", ""),
        ("BeefBurger", ""),
        ("LettuceBurger", ""),
    ]
    legal_chop_targets: List[Tuple[str, str]] = [("Lettuce", "fresh")]
    legal_put_out_targets: List[Tuple[str, str]] = [("Fire", "")]
    legal_drop_targets: List[Tuple[str, str]] = [("Dustbin", "")]
    legal_deliver_targets: List[Tuple[str, str]] = [("DeliverSquare", "")]

    def __init__(self, world: CookingWorld, agent_idx, real_time_plan: bool = True) -> None:
        self.current_task: Callable = None
        self.destination = None
        self.target = ""
        self.target_status = ""
        self.path = None
        self.is_task_to_finish = False
        self.task_step = 0
        self.world = world
        self.agent: Agent = world.agents[agent_idx]
        # ?
        self.agent_idx = agent_idx

        self.prev_task_finish = True
        self.prev_task = ""
        self.prev_target = ""  # unused
        self.prev_target_status = ""  # unused
        self.prev_task_str = ""
        self.next_task_str = ""

        self.error_message = ""
        self.location = None
        self.orientation = None

        self.real_time_plan = real_time_plan

        # To match the content in a container
        self.plate_target = None
        self.assigned_target = None

        self.last_position = None
        self.last_destination = None

    def update_agent(self, world: CookingWorld, agent_idx):
        self.current_task: Callable = None
        self.destination = None
        self.target = ""
        self.target_status = ""
        self.path = None
        self.is_task_to_finish = False
        self.task_step = 0
        self.world = world
        self.agent: Agent = world.agents[agent_idx]
        # ?
        self.agent_idx = agent_idx

        self.prev_task_finish = True
        self.prev_task = ""
        self.prev_target = ""
        self.prev_target_status = ""
        self.prev_task_str = ""
        self.next_task_str = ""

        self.error_message = ""
        self.location = None
        self.orientation = None

        # To match the content in a container
        self.plate_target = None
        self.assigned_target = None

        self.last_position = None
        self.last_destination = None

    def search_valid_position(self, position, for_find_path=False):  # , search_step_left):
        (x, y) = position if position else self.destination
        level_array = self.update_level_array(for_find_path=for_find_path)
        valid_pos_list = []
        for pos in get_neighbor_position((x, y)):
            if pos[0] < 0 or pos[0] >= self.world.width or pos[1] < 0 or pos[1] >= self.world.height:
                continue
            valid_pos_list.append(pos)
        sorted_valid_pos_list = sorted(
            valid_pos_list,
            key=lambda x: (
                level_array[x[0]][x[1]],
                self.distance(x, self.agent.location),
            ),
        )
        for pos in sorted_valid_pos_list:
            if level_array[pos[0]][pos[1]] == 0:
                return pos
            if level_array[pos[0]][pos[1]] == 2:
                return self.search_valid_position(pos)
        return None

    def is_valid_position(self, position=None, search=True, for_find_path=False):  # , max_search_step = 10):
        (x, y) = position if position else self.destination
        # print(self.agent.location, (x, y))
        #        max_search_step = max_search_step if for_find_path else 1
        if self.update_level_array(for_find_path=for_find_path)[x][y] == 1:
            res = self.search_valid_position((x, y)) if search else None
            if res:
                path = find_path(self.agent.location, res, self.update_level_array())
                if len(path) == 0:
                    return None
                else:
                    return res
            else:
                return None
        path = find_path(self.agent.location, (x, y), self.update_level_array())
        if len(path) == 0:
            return None
        return (x, y)

    def is_valid_position_multi(self, position=None, search=True, for_find_path=False):  # , max_search_step = 10):
        (x, y) = position if position else self.destination
        # print(self.agent.location, (x, y))
        # if len(path) == 0:
        #     return None
        #        max_search_step = max_search_step if for_find_path else 1
        if self.update_level_array(for_find_path=for_find_path)[x][y] == 1:
            res = self.search_valid_position((x, y), for_find_path) if search else None
            if res:
                path = find_path(self.agent.location, res, self.update_level_array())
                if len(path) == 0:
                    return None
                else:
                    return res
            else:
                return None
        path = find_path(self.agent.location, (x, y), self.update_level_array())
        if len(path) == 0:
            return None
        return (x, y)

    def turn(self, destination):
        dx = destination[0] - self.agent.location[0]
        dy = destination[1] - self.agent.location[1]
        if dx < 0:
            return 1
        elif dx > 0:
            return 2
        if dy < 0:
            return 4
        elif dy > 0:
            return 3

        if dx == 0 and dy == 0:
            return 0
        return -2

    def update_level_array(self, for_find_path=True):
        level_array = deepcopy(self.world.level_array)
        for agent in self.world.agents:
            if agent == self.agent:
                continue
            (x, y) = agent.location
            level_array[x][y] = 1 if for_find_path else 2

        return level_array

    def update_task(self, function: str, target: Tuple[str, str], message: str):
        target, target_status = target

        self.prev_task_str = message
        self.next_task_str = ""

        if function in ["fetch"]:
            target_str_cap = target if not "Station" in target else target[:-7]
            # logger.debug(target_str_cap)
            if self.agent.holding is not None and not self.is_target(
                self.agent.holding,
                target_str_cap,
                target_status,
                station="Station" in target,
            ):
                function = "put_onto"
                target = "Counter"
                target_status = ""
                self.prev_task_str = "put_onto_counter"
                self.next_task_str = message
        elif function in ["chop"]:
            if self.agent.holding is not None:
                function = "put_onto"
                target = "Counter"
                target_status = ""
                self.prev_task_str = "put_onto_counter"
                self.next_task_str = message

        if function == "fetch":
            self.current_task = self.fetch
        elif function == "plate":
            self.current_task = self.plate
        elif function == "drop":
            self.current_task = self.drop
        elif function == "chop":
            self.current_task = self.chop
        elif function == "putout":
            self.current_task = self.putout
        elif function == "serve":
            self.current_task = self.serve
        elif function == "put_onto":
            self.current_task = self.put_onto
        elif function == "put_onto_center":
            self.current_task = self.put_onto_center
        elif function == "put_onto_edge":
            self.current_task = self.put_onto_edge
        elif function == "move_to":
            self.current_task = self.move_to
        elif function == "wait":
            self.current_task = self.wait
        else:
            raise NotImplementedError(f"Function {function} is not implemented.")

        if function == "move_to":
            self.target = (int(target.split(",")[0]), int(target.split(",")[1]))
        elif function == "wait":
            self.target = int(target)
        else:
            self.target = target
        self.destination = None
        self.target_status = target_status

        self.task_step = 0

        self.prev_task = function
        self.is_task_to_finish = False
        self.prev_task_finish = False

        self.error_message = ""

    def get_task_state(self):
        if self.prev_task is None or self.prev_task == "":
            return f". No previous task."
        elif self.prev_task_finish:
            return f". The preivous task is {self.prev_task}, which is finished."
        elif self.error_message == "":
            return f". The preivous task is {self.prev_task}, which is not finished. If you find your previous task is not finished, you need to continue to finish it or just forget your previous task. It is up to you, but you need consider the previous task when you generate the cureent task."
        else:
            return f". The preivous task is {self.prev_task}, which is not finished. {self.error_message}"

    def get_json_task_state(self):
        json_state = {"name": "", "status": "", "info": ""}
        if self.prev_task is None or self.prev_task == "":
            json_state["name"] = "None"
            json_state["status"] = "finished"
            json_state["info"] = "valid"
        elif self.prev_task_finish:
            json_state["name"] = self.prev_task
            json_state["status"] = "finished"
            json_state["info"] = "valid"
        elif self.error_message == "":
            json_state["name"] = self.prev_task
            json_state["status"] = "in_progress"
            json_state["info"] = "valid"
        else:
            json_state["name"] = self.prev_task
            json_state["status"] = "invalid"
            json_state["info"] = self.error_message

        return json_state

    def get_objects(self, target: str, target_status: str = "", check: Callable = None) -> list:
        assert not (target_status != "" and check is not None), "only one condition"
        if check:
            return [obj for obj in self.world.world_objects[target] if check(obj)]
        return [obj for obj in self.world.world_objects[target] if self.is_target(obj, target, target_status)]

    def get_valid_actions(self):
        # since put_onto_counter is automatic, get and pickup will not check agent.holding
        valid_actions = [
            # "get_plate_from_station",
            # "get_lettuce_from_station",
            # "get_beef_from_station",
            # "get_bread_from_station",
            "wait",
        ]

        # empty hand or at least one empty counter

        # Check
        # 1. is the target
        # 2. placement, represented by the obejcts in the same location
        # 3. can be found (is the destination)
        # 4. agent status (holding)
        empty_counters = self.get_objects("Counter", check=lambda x: len(self.world.get_objects_at(x.location)) == 1)
        empty_counters = [x for x in empty_counters if self.is_destination(x, empty_counters)]
        if self.agent.holding is None or len(empty_counters) > 0:
            # get from station
            for station in self.legal_get_targets:
                station = station[0]
                station_objects = self.get_objects(station)
                for station_object in station_objects:
                    if self.is_destination(station_object, station_objects):
                        valid_actions.append(f"get_{station[:-7].lower()}_from_station")
                        break
            # valid_actions.extend(
            #     [
            #         "get_plate_from_station",
            #         "get_lettuce_from_station",
            #         "get_beef_from_station",
            #         "get_bread_from_station",
            #     ]
            # )

        # Pickup
        for target_str, target_status in self.legal_pickup_targets:

            def check(x):
                return self.is_target(x, target_str, target_status) and (
                    (
                        (
                            (
                                self.is_target(x, "Lettuce", "done")
                                and len(self.world.get_objects_at(x.location, CutBoard)) == 1
                            )
                            or len(self.world.get_objects_at(x.location, Counter)) == 1
                        )
                        and (self.agent.holding is None or len(empty_counters) > 0)
                    )
                    or self.in_agent_hands(x)
                )

            target_objects = self.get_objects(target_str, check=check)
            for obj in target_objects:
                target_list = (
                    target_objects
                    if not (target_status == "fresh" or target_str == "Bread" or target_str == "Plate")
                    else (target_objects + self.world.world_objects[f"{target_str}Station"])
                )
                if self.is_destination(obj, target_list):
                    valid_actions.append(
                        f"pickup_{target_str.lower()}_{target_status}"
                        if target_status != ""
                        else f"pickup_{target_str.lower()}"
                    )
                    break

        if self.agent.holding is not None:
            # Put onto static_objects
            for target_str, target_status in self.legal_put_onto_targets[:5]:
                target_objects = self.get_objects(
                    target_str,
                    check=lambda x: self.world.accepts(x, self.agent.holding)
                    and self.is_target_status(x, target_status),
                )
                for obj in target_objects:
                    if self.is_destination(obj, target_objects):
                        if target_str == "Counter" and target_status != "":
                            valid_actions.append(f"put_onto_{target_status}_{target_str.lower()}")
                        else:
                            valid_actions.append(f"put_onto_{target_str.lower()}")
                        break
            if not isinstance(self.agent.holding, Plate) and not isinstance(self.agent.holding, FireExtinguisher):
                # Put onto Plate
                target_objects = self.get_objects(
                    "Plate",
                    check=lambda x: len(x.content) == 0 and is_mixable(self.agent.holding, x),
                )
                for obj in target_objects:
                    if self.is_destination(obj, target_objects):
                        valid_actions.append("put_onto_plate")
                        break
                # Put onto Plate with Food
                for target_str, target_status in self.legal_put_onto_targets[6:]:
                    target_objects = self.get_objects(
                        target_str,
                        check=lambda x: self.is_target_status(x, target_status)
                        and len(
                            self.world.get_objects_at(x.location, Plate),
                        )
                        == 1
                        and is_food_mixable(self.agent.holding, x),
                    )
                    for obj in target_objects:
                        if self.is_destination(obj, target_objects):
                            valid_actions.append(f"put_onto_plate_with_{target_str.lower()}")
                            break
            elif isinstance(self.agent.holding, Plate):  # has a plate in hand
                # Plate
                for target_str, target_status in self.legal_plate_targets:
                    # Static
                    if target_str in ["CutBoard", "Pan"]:
                        static_to_food = {"Pan": "Beef", "CutBoard": "Lettuce"}
                        target_objects = self.get_objects(
                            target_str,
                            check=lambda x: self.is_target(x.content, static_to_food[target_str], target_status)
                            and is_mixable(x.content, self.agent.holding)
                            and len(self.world.get_objects_at(x.location, Fire)) == 0,
                        )
                        for obj in target_objects:
                            if self.is_destination(obj, target_objects):
                                valid_actions.append(
                                    f"plate_{static_to_food[target_str].lower()}_{target_status}_from_{target_str.lower()}"
                                )
                                break

                        # special case for plate_beef_done_from_pan
                        if (
                            target_str == "Pan"
                            and target_status == "done"
                            and "plate_beef_done_from_pan" not in valid_actions
                        ):
                            done_beef = Beef((-1, -1))
                            done_beef.blend_state = BlenderFoodStates.MASHED
                            target_objects = self.get_objects(
                                target_str,
                                check=lambda x: self.is_target(x.content, "Beef", "fresh")
                                and is_mixable(done_beef, self.agent.holding),
                            )
                            for obj in target_objects:
                                if self.is_destination(obj, target_objects):
                                    valid_actions.append("plate_beef_done_from_pan")
                                    break
                    else:  # Food

                        def check(x) -> bool:
                            if self.is_target(x, target_str, target_status) and is_mixable(x, self.agent.holding):
                                return True
                            return False
                            # if (
                            #     self.is_target(x, target_str, target_status)
                            #     and is_mixable(x, self.agent.holding)
                            #     and len(self.world.get_objects_at(x.location, Counter)) == 1
                            # ):
                            #     return True
                            # return False

                        target_objects = self.get_objects(target_str, check=check)
                        for obj in target_objects:
                            if self.is_destination(obj, target_objects):
                                if target_status == "":
                                    valid_actions.append(f"plate_{target_str.lower()}")
                                else:
                                    valid_actions.append(f"plate_{target_str.lower()}_{target_status}")
                                break

            # drop_food
            # MARK: only allow drop overcooked beef
            if self.is_dropable(self.agent.holding):
                valid_actions.append("drop_food")
            if self.is_target(self.agent.holding, "FireExtinguisher") and len(self.world.world_objects["Fire"]) > 0:
                valid_actions.append("put_out_fire")
            if (
                isinstance(self.agent.holding, Plate)
                and len(self.agent.holding.content) > 0
                and type(self.agent.holding.content[0])
                in [
                    BeefLettuceBurger,
                    BeefBurger,
                    LettuceBurger,
                ]
            ):
                valid_actions.append("deliver")

        # Chop, put_onto_counter will be automatically taked
        for target_str, target_status in self.legal_chop_targets:
            target_objects = self.get_objects(
                "CutBoard",
                check=lambda x: self.is_target(x.content, target_str, target_status),
            )
            for obj in target_objects:
                if self.is_destination(obj, target_objects):
                    valid_actions.append("chop_lettuce")
                    break
        return valid_actions

    def is_dropable(self, holding: Object):
        # if (
        #     isinstance(holding, Plate)
        #     and len(holding.content) > 0
        #     and self.is_target(holding.content[0], "Beef", "overcooked")
        # ):
        #     return True
        if (isinstance(holding, Plate) and len(holding.content) > 0) or isinstance(holding, Food):
            return True
        return False

    def take_one_action(self) -> int:
        # Not task
        if self.current_task is None:
            return -1
        if self.real_time_plan and not self.is_task_to_finish:
            self.destination = None
        action = (
            self.current_task(self.target)
            if self.prev_task not in ["fetch", "plate", "put_onto"]
            else self.current_task(self.target, self.target_status)
        )
        if action >= 0:
            self.task_step += 1
        elif self.next_task_str != "":
            func, target = self.get_instruction(self.next_task_str)
            self.update_task(func, target, self.next_task_str)
            action = (
                self.current_task(self.target)
                if self.prev_task not in ["fetch", "plate", "put_onto"]
                else self.current_task(self.target, self.target_status)
            )
        return action

    def get_instruction(self, message) -> Tuple[str, Tuple[str, str]]:
        assert message in self.legal_text_actions, message
        func = ""
        target = ""
        target_status = ""
        if "from_station" in message:
            target_str = message.split("_")[-3]
            target_str_cap = TextToCap[target_str]
            func = "fetch"
            target = f"{target_str_cap}Station"

        elif "pickup" in message:
            task_tuple = message.split("_", 2)
            target_str = task_tuple[1]
            target_str_cap = TextToCap[target_str]
            if len(task_tuple) == 2:
                func = "fetch"
                target = target_str_cap
            else:
                target_status = task_tuple[2]
                assert target_status in ["fresh", "done", "overcooked", "in_plate"]
                assert hasattr(StringToClass[target_str_cap], target_status) or (
                    target_str_cap in ["Lettuce", "Bread"] and target_status in ["in_plate"]
                )
                func = "fetch"
                target = target_str_cap

        elif "put_onto" in message:
            target_tuple = message.split("_")
            if len(target_tuple) == 3:
                target_str = target_tuple[2]
                target_str_cap = TextToCap[target_str]
                func = "put_onto"
                target = target_str_cap
            elif len(target_tuple) == 4:
                target_str = target_tuple[3]
                target_str_cap = TextToCap[target_str]
                func = "put_onto"
                target = target_str_cap
                target_status = target_tuple[2]
            else:
                # MARK: plate function should check the plate
                target_str = target_tuple[4]
                target_str_cap = TextToCap[target_str]
                func = "put_onto"
                target = target_str_cap
                put_onto_target_to_status = {
                    "Beef": "done",
                    "Lettuce": "done",
                }
                if target in put_onto_target_to_status:
                    target_status = put_onto_target_to_status[target]

        elif "plate" in message:
            target_tuple = message.split("_")
            func = "plate"
            target_str = target_tuple[1]
            if len(target_tuple) in [3, 5]:
                target_status = target_tuple[2]
                assert target_status in ["done", "overcooked"]
            if len(target_tuple) == 5:
                target_str = target_tuple[4]
            target_str_cap = TextToCap[target_str]
            target = target_str_cap
            if target in ["Lettuce", "CutBoard"]:
                target_status = "done"

        elif "chop" in message:
            if "chop_lettuce" in message:
                func = "chop"
                target = "Lettuce"
        elif "put_out" in message:
            if "put_out_fire" in message:
                func = "putout"
                target = "Fire"
        elif "deliver" in message:
            func = "serve"
            target = "DeliverSquare"
        elif "drop" in message:
            func = "drop"
            target = "Dustbin"
        elif "wait" in message:
            func = "wait"
            target = 5
        else:
            raise NotImplementedError(f"Text action {message} is not implemented.")

        return func, (target, target_status)

    def distance(self, location1, location2):
        return abs(location1[0] - location2[0]) + abs(location1[1] - location2[1])

    def sort_object_by_distance(self, objects, source_location=None):
        target_location = self.agent.location

        objects.sort(key=lambda x: self.distance(x.location, target_location))
        # objects.sort(
        #     key=lambda x: len(
        #         self.findpath(
        #             x.location,
        #             source_location,
        #         )
        #     )
        # )
        return objects

    def sort_object_by_urgence(self, objects, source_location=None):
        if not all([hasattr(obj, "current_progress") for obj in objects]):
            return self.sort_object_by_distance(objects, source_location)
        objects.sort(key=lambda x: x.current_progress)

        return objects

    # def findpath(self, target_location, source_location=None) -> list:
    #     if source_location is None:
    #         source_location = self.agent.location
    #     target_location = self.is_valid_position(target_location, for_find_path=True)
    #     if target_location:
    #         return find_path(
    #             source_location,
    #             target_location,
    #             self.update_level_array(),
    #         )
    #     return sum(self.world.level_array.shape) * 2 * [(-1, -1)]

    def closest(self, objects: List, target_location=None) -> Tuple[Object, int]:
        assert len(objects) > 0, objects
        if target_location is None:
            target_location = self.agent.location
        closet_object = self.sort_object_by_distance(objects, target_location)[0]
        # return closet_object, len(
        #     self.findpath(closet_object.location, target_location)
        # )
        return closet_object, self.distance(closet_object.location, target_location)

    def is_target(self, holding, target: str, target_status: str = "", station: bool = False) -> bool:
        if holding is None:
            return False
        if isinstance(target, str):
            target = StringToClass.get(target)
        if isinstance(holding, Container):
            if len(holding.content) == 0:
                return isinstance(holding, target)
            else:
                holding = holding.content[0]
        return (isinstance(holding, target) and not station) and self.is_target_status(holding, target_status)

    def in_other_agent_hands(self, target: Object) -> bool:
        for agent in self.world.agents:
            if agent == self.agent:
                continue
            if agent.holding is target:
                return True
            if (
                isinstance(agent.holding, Container)
                and len(agent.holding.content) > 0
                and agent.holding.content[0] is target
            ):
                return True
        return False

    def in_agent_hands(self, target: Object) -> bool:
        if self.agent.holding is target:
            return True
        if (
            isinstance(self.agent.holding, Container)
            and len(self.agent.holding.content) > 0
            and self.agent.holding.content[0] is target
        ):
            return True
        return False

    def is_target_status(self, target: Object, target_status: str) -> bool:
        assert not isinstance(target, Container) or len(target.content) == 0
        target_status_to_callable = {
            "in_plate": lambda x: len(self.world.get_objects_at(x.location, Plate)) == 1
            and isinstance(x, Food)
            and self.is_target_status(x, "done"),  # avoid overcooked beef
            "edge": lambda x: isinstance(x, Counter) and x.is_center == False,
            "center": lambda x: isinstance(x, Counter) and x.is_center == True,
            "overcooked": lambda x: x.overcooked() is True and len(self.world.get_objects_at(x.location, Fire)) == 0,
        }
        if target_status in target_status_to_callable:
            return target_status_to_callable[target_status](target)
        else:
            return not target_status or getattr(target, target_status, lambda: False)()

    def get_dynamic_target_status(self, target: Object) -> str:
        # only for dynamic objects
        if isinstance(target, (Beef, Lettuce)):
            if getattr(target, "done", lambda: False)():
                return "done"
            if getattr(target, "overcooked", lambda: False)():
                return "overcooked"
            return "fresh"
        return ""

    def is_destination(self, target: Object, target_list: list) -> bool:
        if (
            (len(target_list) == 1 and self.is_valid_position(target.location, for_find_path=True))
            or (len(target_list) > 1 and self.is_valid_position_multi(target.location, for_find_path=True))
        ) and not self.in_other_agent_hands(target):
            return True
        return False

    def is_in_content(self, target: Object, holding: Object):
        assert isinstance(target, Food) and isinstance(holding, Food), (
            type(target),
            type(holding),
        )
        if not hasattr(target, "content"):
            if not hasattr(holding, "content"):
                return False
            else:
                return target.file_name() in holding.content
        else:
            c_t = Cnter(target.content)
            if not hasattr(holding, "content"):
                return False
            c_h = Cnter(holding.content)

            for c in c_t:
                if c_t[c] > c_h[c]:
                    return False
            return True

    def fetch(self, target: str, target_status: str):
        """
        fetch things that on somewhere or in station.
        example:
        fetch(world, destination, 'Tomato')
        fetch(world, destination,  )
        target: Station or something can be fetched
        """
        assert (target, target_status) in self.legal_get_targets or (
            target,
            target_status,
        ) in self.legal_pickup_targets, (target, target_status)
        if self.is_task_to_finish:
            self.is_task_to_finish = False
            if (
                self.is_target(self.agent.holding, target, target_status)
                or (StringToClass.get(target, None) == BeefStation and self.agent.holding.__class__ == Beef)
                or (StringToClass.get(target, None) == BreadStation and self.agent.holding.__class__ == Bread)
                or (StringToClass.get(target, None) == LettuceStation and self.agent.holding.__class__ == Lettuce)
                or (StringToClass.get(target, None) == PlateStation and self.agent.holding.__class__ == Plate)
            ):
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                self.assigned_target = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                self.assigned_target = None
                return -2

        # if not self.destination:
        if self.real_time_plan or not self.destination:
            target_cls = StringToClass.get(target, None)
            if target_cls is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                self.assigned_target = None
                return -2
            if self.agent.holding is not None:
                self.is_task_to_finish = True
                return 0

            def check(x) -> bool:
                return (
                    self.is_target(x, target, target_status)
                    and (
                        (
                            self.is_target(x, "Lettuce", "done")
                            or len(self.world.get_objects_at(x.location, CutBoard)) == 0
                        )
                        or (
                            len(self.world.get_objects_at(x.location, Counter))
                            + len(self.world.get_objects_at(x.location, Station))
                            == 1  # not in Pan
                        )
                    )
                    and (not isinstance(x, Container) or len(x.content) == 0)  # only food and empty plate can be pickup
                )

            target_object = self.get_objects(target, check=check)
            if len(target_object) == 0:
                self.error_message = f"There is no {target} currently."
                if target in ["Beef", "Lettuce", "Plate", "Bread"]:
                    self.error_message += " You may need to get from station."
                self.current_task = None
                self.prev_task = None
                self.assigned_target = None
                return -2
            else:
                target_object = self.sort_object_by_distance(target_object)
                # logger.error(self.assigned_target)
                if (
                    self.assigned_target is not None
                    and self.assigned_target in target_object
                    and self.is_destination(self.assigned_target, target_object)
                ):
                    # logger.error(self.assigned_target)
                    target_object = self.assigned_target
                    self.destination = target_object.location
                else:
                    for i, obj in enumerate(target_object):
                        if self.is_destination(obj, target_object):
                            target_object = obj
                            self.destination = target_object.location
                            break
            if self.destination is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                self.assigned_target = None
                return -2
        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)

        if shifted_location == self.destination:
            # fetch the object (interact)
            self.is_task_to_finish = True
            return 5

        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                # print("valid_position", self.is_valid_position(for_find_path=True))
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    def plate(self, target, target_status: str):
        """
        plate food from pan, counter, cutboard
        target: Food
        """
        assert (target, target_status) in self.legal_plate_targets, (
            target,
            target_status,
        )
        if self.is_task_to_finish:
            self.is_task_to_finish = False
            if (
                isinstance(self.agent.holding, Plate)
                and len(self.agent.holding.content) > 0
                and (
                    self.is_target(
                        self.agent.holding.content[0],
                        StringToClass.get(self.plate_target.file_name()),
                        target_status,
                    )
                    or self.is_in_content(self.plate_target, self.agent.holding.content[0])
                )
            ):
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -2
        # if not self.destination:
        if self.real_time_plan or not self.destination:
            if not isinstance(self.agent.holding, Plate):
                self.current_task = None
                self.prev_task = None
                self.error_message = "You do not have a plate in hand."
                return -2
            target_cls = StringToClass.get(target, None)
            if target_cls is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2
            # target_object = self.world.world_objects[target]
            if issubclass(StringToClass[target], StaticObject):
                static_to_food = {"Pan": "Beef", "CutBoard": "Lettuce"}
                target_object = self.get_objects(
                    target,
                    check=lambda x: self.is_target(x.content, static_to_food[target], target_status),
                )
                if target == "Pan" and target_status == "done":
                    target_object += self.get_objects(
                        target,
                        check=lambda x: self.is_target(x.content, "Beef", "fresh"),
                    )
            else:
                target_object = self.get_objects(
                    target,
                    check=lambda x: self.is_target(
                        x,
                        target,
                        target_status,
                    ),
                )
                # target_object = self.get_objects(
                #     target,
                #     check=lambda x: self.is_target(
                #         x,
                #         target,
                #         target_status,
                #     )
                #     and len(self.world.get_objects_at(x.location, Counter)) == 1,
                # )

            if len(target_object) == 0:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2
            else:
                # target_object = self.sort_object_by_distance(target_object)
                target_object = self.sort_object_by_urgence(target_object)
                target_object = sorted(
                    target_object,
                    key=lambda x: (
                        1 if getattr(x, "done", lambda: False)() or (hasattr(x, "content") and x.content.done()) else 2
                    ),
                )
                for i, obj in enumerate(target_object):
                    if self.is_destination(obj, target_object):
                        target_object = obj
                        self.destination = target_object.location
                        if isinstance(obj, StaticObject):
                            self.plate_target = target_object.content
                        else:
                            self.plate_target = target_object
                        break
            if self.destination is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2

        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)
        if shifted_location == self.destination:
            if self.is_target(self.plate_target, "Beef", "fresh"):
                return 0
            else:
                self.is_task_to_finish = True
                return 5
        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    def drop(self, target):
        """
        drop things into dustbin
        target: Dustbin
        """
        assert target in [l_t[0] for l_t in self.legal_drop_targets]
        if self.is_task_to_finish:
            self.is_task_to_finish = False
            if self.agent.holding is None or (
                isinstance(self.agent.holding, Plate) and len(self.agent.holding.content) == 0
            ):
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -2
        # if not self.destination:
        if self.real_time_plan or not self.destination:
            if self.agent.holding is None:
                self.current_task = None
                self.prev_task = None
                self.error_message = "You have something in hand."
                return -2
            if isinstance(self.agent.holding, Plate):
                if len(self.agent.holding.content) == 0:
                    self.current_task = None
                    self.prev_task = None
                    self.error_message = "You can not drop an empty plate."
                    return -2
            elif not isinstance(self.agent.holding, Food):
                self.current_task = None
                self.prev_task = None
                self.error_message = "You can only drop food."
                return -2
            target_cls = StringToClass.get(target, None)
            if target_cls != Dustbin:
                self.error_message = "Your target is not Dustbin"
                self.current_task = None
                self.prev_task = None
                return -2
            target_object = self.world.world_objects[target]
            if len(target_object) == 0:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2
            else:
                target_object = self.sort_object_by_distance(target_object)
                for i, obj in enumerate(target_object):
                    if self.is_destination(obj, target_object):
                        target_object = obj
                        self.destination = target_object.location
                        break
            if self.destination is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2
        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)
        if shifted_location == self.destination:
            # drop the object (interact)
            self.is_task_to_finish = True
            return 5
        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    def chop(self, target):
        """
        chop food on cutboard
        target: Food
        """
        assert target in [l_t[0] for l_t in self.legal_chop_targets]
        if self.is_task_to_finish:
            target_cls = StringToClass.get(target, None)
            target_object = self.world.get_objects_at(self.destination, target_cls)[0]
            if target_object.chop_num == target_object.max_chop_num:
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -2
        # if not self.destination:
        if self.real_time_plan or not self.destination:
            # has_chopped_thing = False
            if self.agent.holding is not None:
                self.current_task = None
                self.prev_task = None
                self.error_message = "You can not chop when you have something in hand."
                # print('you can not chop without hand')
                return -2
            target_cls = StringToClass.get(target, None)
            if target_cls is None or target_cls not in CHOPFOOD2LABEL.keys():
                self.error_message = "Your target can not be chopped"
                self.current_task = None
                self.prev_task = None
                return -2
            # target_object = self.world.world_objects[target]
            cutboards = self.get_objects("CutBoard", check=lambda cb: self.is_target(cb.content, target, "fresh"))
            if len(cutboards) == 0:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2

            # find if the target location is Cutboard
            cutboards = self.sort_object_by_distance(cutboards)
            for i, cb in enumerate(cutboards):
                if self.is_destination(cb, cutboards):
                    self.destination = cb.location
                    target_object = cb
                    break
            if not self.destination:
                self.error_message = "Can not find target on cutboard"
                self.current_task = None
                self.prev_task = None
                return -2
        target_cls = StringToClass.get(target, None)
        target_objects = self.world.get_objects_at(self.destination, target_cls)
        if len(target_objects) == 0:
            self.error_message = "Can not find valid object."
            self.destination = None
            self.current_task = None
            self.prev_task = None
            return -2
        target_object = self.world.get_objects_at(self.destination, target_cls)[0]
        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)
        if shifted_location == self.destination:
            # chop the object (interact)
            if target_object.chop_num == target_object.max_chop_num - 1:
                self.is_task_to_finish = True
            return 5
        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    def putout(self, target):
        """
        putout fire
        target: Fire
        put out all the Fires
        """
        if self.is_task_to_finish:
            target_cls = StringToClass.get(target, None)
            target_object = self.world.get_objects_at(self.destination, target_cls)
            if len(target_object) == 0:
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -2
        # if not self.destination:
        if self.real_time_plan or not self.destination:
            if self.agent.holding is None or not isinstance(self.agent.holding, FireExtinguisher):
                self.error_message = "You do not have fire extinguisher in hand."
                self.current_task = None
                self.prev_task = None
                return -2
            target_cls = StringToClass.get(target, None)
            if target_cls is None or target_cls != Fire:
                self.error_message = "Your target is not fire"
                self.current_task = None
                self.prev_task = None
                return -2
            target_object = self.world.world_objects[target]
            if len(target_object) == 0:
                self.current_task = None
                self.prev_task = None
                self.error_message = "Can not find valid object."
                return -2
            else:
                target_object = self.sort_object_by_distance(target_object)
                for i, obj in enumerate(target_object):
                    if self.is_destination(obj, target_object):
                        target_object = obj
                        self.destination = target_object.location
                        break
            if self.destination is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2
        target_cls = StringToClass.get(target, None)
        target_object = self.world.get_objects_at(self.destination, target_cls)[0]
        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)
        if shifted_location == self.destination:
            if target_object.put_num == target_object.max_put_num - 1:
                if len(self.world.world_objects[target]) > 1:
                    self.destination = None
                else:
                    self.is_task_to_finish = True
            return 5
        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    def serve(self, target):
        """
        serve object on hand to deliver
        target: DeliverSquare
        """
        if self.is_task_to_finish:
            if self.agent.holding is None:
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                return -2
        # if not self.destination:
        if self.real_time_plan or not self.destination:
            if self.agent.holding is None:
                self.error_message = "You have nothing in hand."
                self.current_task = None
                self.prev_task = None
                return -2
            if not isinstance(self.agent.holding, Plate) or len(self.agent.holding.content) == 0:
                self.error_message = "You can only serve burger."
                self.current_task = None
                self.prev_task = None
                return -2
            target_cls = StringToClass.get(target, None)
            if target_cls is None or target_cls != DeliverSquare:
                self.error_message = "Your target is not deliversquare"
                self.current_task = None
                self.prev_task = None
                return -2
            target_object = self.world.world_objects[target]
            if len(target_object) == 0:
                self.current_task = None
                self.prev_task = None
                self.error_message = "Can not find valid object."
                return -2
            else:
                target_object = self.sort_object_by_distance(target_object)
                for i, obj in enumerate(target_object):
                    if self.is_destination(obj, target_object):
                        target_object = obj
                        self.destination = target_object.location
                        break
            if self.destination is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                return -2
        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)
        if shifted_location == self.destination:
            self.is_task_to_finish = True
            return 5
        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    # def put_onto_center(self, target):
    #     return self.put_onto(target, for_passon=True, is_center=True)

    # def put_onto_edge(self, target):
    #     return self.put_onto(target, for_passon=True, is_center=False)

    # def put_onto(self, target, for_passon: bool = False, is_center: bool = True):
    def put_onto(self, target: str, target_status: str):
        """
        put object on hand onto target
        example:
        cook(world, destination, 'Pan')
        if you want to mix food, please use that food as target
        target: pot, counter or mixable food
        """
        assert (
            target,
            target_status,
        ) in self.legal_put_onto_targets, f"{(target, target_status)} not in {self.legal_put_onto_targets}"
        if self.is_task_to_finish:
            if self.agent.holding is None:
                self.prev_task_finish = True
                self.current_task = None
                self.prev_task = None
                self.destination = None
                self.assigned_target = None
                return -1
            else:
                self.prev_task_finish = False
                self.current_task = None
                self.prev_task = None
                self.destination = None
                self.assigned_target = None
                return -2
        # if not self.destination:
        if self.real_time_plan or not self.destination:
            if self.agent.holding is None:
                self.error_message = "You have nothing in hand."
                self.current_task = None
                self.prev_task = None
                self.assigned_target = None

                return -2
            target_cls = StringToClass.get(target, None)
            if target_cls is None or (not target == "Counter" and isinstance(self.agent.holding, Plate)):
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                self.assigned_target = None
                return -2
            if issubclass(target_cls, StaticObject):
                target_object = self.get_objects(
                    target,
                    check=lambda x: len(self.world.get_objects_at(x.location)) == 1
                    and (not isinstance(x, Counter) or self.is_target_status(x, target_status)),
                )
            elif issubclass(target_cls, Food):
                target_object = self.get_objects(
                    target,
                    check=lambda x: len(self.world.get_objects_at(x.location, Plate)) == 1
                    and self.is_target_status(x, target_status),
                )
            elif issubclass(target_cls, Container):
                target_object = self.get_objects(target, check=lambda x: len(x.content) == 0)
            else:
                target_object = self.world.world_objects[target]
            # if target == "Counter":
            #     remove_location = [(0, 0), (7, 0), (7, 6), (0, 6)]
            #     target_object = [x for x in target_object if (x.location not in remove_location)]
            # for pass on
            # if for_passon is True:
            #     target_object = [x for x in target_object if (x.is_center == is_center)]
            if len(target_object) == 0:
                self.current_task = None
                self.prev_task = None
                self.error_message = "Can not find valid object."
                self.assigned_target = None
                return -2
            else:
                target_object = self.sort_object_by_distance(target_object)
                if (
                    self.assigned_target is not None
                    and self.assigned_target in target_object
                    and self.is_destination(self.assigned_target, target_object)
                ):
                    target_object = self.assigned_target
                    self.destination = target_object.location
                else:
                    for i, obj in enumerate(target_object):
                        if self.is_destination(obj, target_object):
                            target_object = obj
                            self.destination = target_object.location
                            break
            if self.destination is None:
                self.error_message = "Can not find valid object."
                self.current_task = None
                self.prev_task = None
                self.assigned_target = None
                return -2
        shifted_location = self.world.get_target_location(self.agent, self.agent.orientation)
        if shifted_location == self.destination:
            self.is_task_to_finish = True
            return 5
        if self.destination in get_neighbor_position(self.agent.location):
            return self.turn(self.destination)
        else:
            if self.is_valid_position(for_find_path=True):
                path: List[Tuple[int, int]] = find_path(
                    self.agent.location,
                    self.is_valid_position(for_find_path=True),
                    self.update_level_array(),
                )
                if len(path) == 1:
                    return 0
                if len(path) == 0:
                    # raise
                    return -2
                # return self.move_to(path[1])
                return self.move_to(self.is_valid_position(for_find_path=True))
            else:
                return 0

    def move_to(self, destination: Tuple[int, int]) -> bool:
        """move to the specified destination
        Args:
            destination (Tuple[int, int]): 2D coordinate of the destination
        Returns:
            bool: True when the agent has reached the destination
        """
        if not self.destination:
            if destination == self.agent.location:
                # print("arrived")
                self.current_task = None
                self.prev_task = None
                return -2
            if self.is_valid_position(destination, search=False):
                self.destination = destination
            else:
                # print("invalid destination")
                self.current_task = None
                self.prev_task = None
                return -2
        if destination == self.agent.location:
            return 0
        if destination in get_neighbor_position(self.agent.location):
            for agent in self.world.agents:
                if agent == self.agent:
                    continue
                if agent.location == destination:
                    return 0
            if self.current_task == self.move_to:
                self.current_task = None
                self.prev_task = None
                self.destination = None
            return self.turn(destination)
        path: List[Tuple[int, int]] = find_path(
            self.agent.location,
            self.is_valid_position(for_find_path=True),
            self.update_level_array(),
        )
        if len(path) == 1:
            self.last_position = self.agent.location
            self.last_destination = self.agent.location
            return 0
        if len(path) == 0:
            # raise
            return -2
        if path[1] in [self.last_destination, self.last_position]:
            possible_moves = get_neighbor_position(self.agent.location)
            if path[1] in possible_moves:
                possible_moves.remove(path[1])
            valid_moves = []
            for p_move in possible_moves:
                if self.is_valid_position(p_move, for_find_path=True):
                    valid_moves.append(p_move)
            move = random.choice(valid_moves + [(0, 0)])
            self.last_position = self.agent.location
            self.last_destination = path[1]
            return self.turn(move)
        self.last_position = self.agent.location
        self.last_destination = path[1]
        return self.turn(path[1])

    def wait(self, target):
        if target <= 0:
            self.current_task = None
            self.prev_task = None
            # logger.warning("invalid wait turns")
            return -2
        self.target -= 1
        if self.target <= 1:
            self.current_task = None
            self.prev_task = None
            return -1
        return 0
