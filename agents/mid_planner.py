import random
from collections import defaultdict
from typing import Callable, Dict, List, Tuple, Union

from gym_cooking.cooking_world.cooking_world import CookingWorld
from gym_cooking.cooking_world.world_objects import *
from loguru import logger
from rich.pretty import pretty_repr

from agents.text_agent import TextAgent


# MARK: Have not considered whether the target is blocked by human yet.
def is_pan_available(agent: TextAgent, world: CookingWorld) -> bool:
    """
    Check whether there is an available pan.
    """

    def check(x) -> bool:
        return x.content is None

    return len(agent.get_objects("Pan", check=check)) > 0


def is_cutboard_available(agent: TextAgent, world: CookingWorld):
    """
    Check whether there are chopped lettuces on all cutboards.
    """
    return len(
        agent.get_objects(
            "CutBoard",
            check=lambda x: agent.is_target(x.content, "Lettuce", "done"),
        )
    ) < len(agent.get_objects("CutBoard"))


def is_ingredients_available(
    agent: TextAgent,
    world: CookingWorld,
    targets: List[str],
    target_status_list: List[Union[str, Callable]],
) -> bool:
    """
    `targets`: a list of prepared ingredients for assembling burgers
    """
    # assert len(target_status_list) == len(targets) or len(target_status_list) == 0
    assert len(target_status_list) == len(targets)
    assert all([isinstance(t_s, str) or isinstance(t_s, Callable) for t_s in target_status_list])
    # if len(target_status_list) == 0:
    #     target_status_list = ["" for _ in range(len(targets))]
    for target, target_status in zip(targets, target_status_list):
        if target in TextToCap:
            logger.error(f"TextToCap is used for {target}")
            target = TextToCap[target]
        if isinstance(target_status, str):
            target_objects = agent.get_objects(target, target_status)
        else:
            target_objects = agent.get_objects(target, check=target_status)
        cnt = 0
        for obj in target_objects:
            if agent.is_destination(obj, target_objects):
                cnt += 1
        if cnt == 0:
            return False
    return True


def is_cutboard_ready(agent: TextAgent, world: CookingWorld):
    """
    Check whether there is a chopped lettuce on a cutboard.
    """
    return (
        len(
            agent.get_objects(
                "CutBoard",
                check=lambda x: agent.is_target(x.content, "Lettuce", "done"),
            )
        )
        > 0
    )


def is_pan_ready(agent: TextAgent, world: CookingWorld):
    """
    Check whether there is a cooking beef on a Pan.
    """
    return (
        len(
            agent.get_objects(
                "Pan",
                check=lambda x: agent.is_target(x.content, "Beef", "done")
                or agent.is_target(x.content, "Beef", "fresh"),
            )
        )
        > 0
    )


def is_on_fire(agent: TextAgent, world: CookingWorld) -> bool:
    """
    Check whether there is a pan on fire.
    """
    return len(agent.get_objects("Fire")) > 0


def is_closest_to_ready_pan(
    agent: TextAgent,
    world: CookingWorld,
    target: str,
    target_status: Union[str, Callable],
) -> bool:
    """
    Check whether the obj is closest to a ready pan among the obj, the PlateStation and empty plates.

    Return
    False if not target objects
    True if not ready pans
    Otherwise return whether the obj is closest to a ready pan among the obj, the PlateStation and empty plates.
    """
    if isinstance(target_status, str):
        target_objects = agent.get_objects(target, target_status)
    else:
        target_objects = agent.get_objects(target, check=target_status)
    if len([obj for obj in target_objects if agent.is_destination(obj, target_objects)]) == 0:
        return False
    target_obj, target_to_agent = agent.closest(
        [obj for obj in target_objects if agent.is_destination(obj, target_objects)]
    )
    if agent.in_agent_hands(target_obj):
        return True
    plate_objects = agent.get_objects("Plate", check=lambda x: len(x.content) == 0) + agent.get_objects("PlateStation")

    if len([obj for obj in plate_objects if agent.is_destination(obj, plate_objects)]) == 0:
        return False
    plate_obj, plate_to_agent = agent.closest(
        [obj for obj in plate_objects if agent.is_destination(obj, plate_objects)]
    )

    pan_objects = agent.get_objects(
        "Pan",
        check=lambda x: agent.is_target(x.content, "Beef", "done") or agent.is_target(x.content, "Beef", "fresh"),
    )
    if len(pan_objects) == 0:
        return True
    # the reachability may change, but I have no idea how to deal with it
    _, target_to_pan = agent.closest(pan_objects, target_obj.location)
    _, plate_to_pan = agent.closest(pan_objects, plate_obj.location)

    return target_to_agent + target_to_pan < plate_to_agent + plate_to_pan


def get_empty_counter(agent: TextAgent, world: CookingWorld) -> List[Counter]:
    return agent.get_objects("Counter", check=lambda x: len(world.get_objects_at(x.location)) == 1)


def get_occupy_counter(agent: TextAgent, world: CookingWorld) -> List[Counter]:
    return agent.get_objects("Counter", check=lambda x: len(world.get_objects_at(x.location)) > 1)


class MidPlanner:
    valid_actions = {
        "prepare": [
            {"food": "Lettuce"},
            {"food": "Lettuce", "plate": False},
            {"food": "Lettuce", "plate": True},
            {"food": "Beef"},
            {"food": "Beef", "plate": False},
            {"food": "Beef", "plate": True},
            {"food": "Bread"},
            {"food": "Bread", "plate": False},
            {"food": "Bread", "plate": True},
        ],
        "assemble": [
            {"food": "BeefLettuce"},
            {"food": "LettuceBurger"},
            {"food": "BeefBurger"},
            {"food": "BeefLettuceBurger"},
        ],
        "serve": [
            {"food": "BeefBurger"},
            {"food": "LettuceBurger"},
            {"food": "BeefLettuceBurger"},
        ],
        "putout_fire": [{}],
        "pass_on": [{"thing": thing, "thing_status": status} for (thing, status) in TextAgent.legal_pickup_targets]
        + [{"thing": thing} for (thing, status) in TextAgent.legal_pickup_targets if status == ""],
        "clean_a_counter": [{"center": False}, {"center": True}],
    }

    def __init__(self, agent: TextAgent, world: CookingWorld, max_n_try: int = 10):
        self.text_agent = agent
        self.agent = agent.agent
        self.agent_idx = self.text_agent.agent_idx
        self.world = world
        self.prev_subtasks: List[str] = []
        self.prev_task: tuple = None
        self.max_n_try = max_n_try

        self._assemble_prev_recipes: List[Tuple[str]] = []

        # Two methods to check state: valid action, check function
        self._prepare_process = {
            "Lettuce": {
                True: [  # priority
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_cutboard_available(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done_from_cutboard",
                        (
                            "get_lettuce_from_station",
                            lambda: is_cutboard_available(self.text_agent, self.world),
                            (),
                        ),
                        "put_onto_cutboard",
                        "chop_lettuce",
                        (
                            "get_plate_from_station",
                            is_cutboard_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done_from_cutboard",
                    ],
                    [
                        "chop_lettuce",
                        (
                            "get_plate_from_station",
                            is_cutboard_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done_from_cutboard",
                    ],
                    [
                        (
                            "get_lettuce_from_station",
                            lambda: is_cutboard_available(self.text_agent, self.world),
                            (),
                        ),
                        "put_onto_cutboard",
                        "chop_lettuce",
                        (
                            "get_plate_from_station",
                            is_cutboard_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done_from_cutboard",
                    ],
                ],
                False: [
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_cutboard_available(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done_from_cutboard",
                        (
                            "get_lettuce_from_station",
                            lambda: is_cutboard_available(self.text_agent, self.world),
                            (),
                        ),
                        "put_onto_cutboard",
                        "chop_lettuce",
                    ],
                    [
                        "chop_lettuce",
                    ],
                    [
                        (
                            "get_lettuce_from_station",
                            lambda: is_cutboard_available(self.text_agent, self.world),
                            (),
                        ),
                        "put_onto_cutboard",
                        "chop_lettuce",
                    ],
                ],
            },
            "Beef": {
                True: [
                    [
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_pan_available(agent, world)
                            and is_ingredients_available(agent, world, ["Beef"], ["overcooked"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_overcooked_from_pan",
                        "drop_food",
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                    [  # no dustbin
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_pan_available(agent, world)
                            and is_ingredients_available(agent, world, ["Beef"], ["overcooked"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_overcooked_from_pan",
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_pan_available(agent, world) and is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done_from_pan",
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                ],
                False: [
                    [
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_pan_available(agent, world)
                            and is_ingredients_available(agent, world, ["Beef"], ["overcooked"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_overcooked_from_pan",
                        "drop_food",
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                    ],
                    [  # no dustbin
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_pan_available(agent, world)
                            and is_ingredients_available(agent, world, ["Beef"], ["overcooked"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_overcooked_from_pan",
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: not is_pan_available(agent, world) and is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done_from_pan",
                        (
                            "get_beef_from_station",
                            is_pan_available,
                            (self.text_agent, self.world),
                        ),
                        "put_onto_pan",
                    ],
                ],
            },
            "Bread": {
                True: [
                    [
                        "get_bread_from_station",
                        "put_onto_plate",
                    ],
                    [
                        "get_bread_from_station",
                        "put_onto_counter",
                        (
                            "get_plate_from_station",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Bread"], [""]),
                        ),
                        "plate_bread",
                    ],
                ],
                False: [
                    [
                        "get_bread_from_station",
                    ]
                ],
            },
        }
        assert self._check_process(self._prepare_process)
        self._prepare_process_forward_index = self._processes_transform(self._prepare_process)
        logger.trace("\n" + pretty_repr(self._prepare_process_forward_index))

        # MARK: priority, first bread on counter, then no bread on counter
        self._num_assemble_process = {
            "LettuceBurger": {
                ("Lettuce",): 7,
            },
            "BeefBurger": {
                ("Beef",): 8,
            },
            "BeefLettuceBurger": {
                ("Beef", "LettuceBurger"): 4,
                ("BeefLettuce",): 3,
                ("BeefBurger", "Lettuce"): 1,
            },
            "BeefLettuce": {
                ("Beef", "Lettuce"): 4,
            },
        }
        self.food_ingredients_index = {
            "LettuceBurger": {
                (): [("LettuceBurger", ["Lettuce"], ["done"])],
                (
                    (
                        "LettuceBurger",
                        ("Lettuce",),
                    ),
                ): True,
            },
            "BeefBurger": {
                (): [
                    (
                        "BeefBurger",
                        ["Beef"],
                        [
                            lambda x: is_pan_ready(self.text_agent, self.world)
                            or self.text_agent.is_target_status(x, "done"),
                        ],
                    ),
                ],
                (
                    (
                        "BeefBurger",
                        ("Beef",),
                    ),
                ): True,
            },
            "BeefLettuce": {
                (): [
                    (
                        "BeefLettuce",
                        ["Beef", "Lettuce"],
                        [
                            lambda x: is_pan_ready(self.text_agent, self.world)
                            or self.text_agent.is_target_status(x, "done"),
                            "done",
                        ],
                    ),  # make a BeefLettuce\
                ],
                (("BeefLettuce", ("Beef", "Lettuce")),): True,
            },
            "BeefLettuceBurger": {
                (): [
                    (
                        "BeefLettuce",
                        ["Beef", "Lettuce"],
                        [
                            lambda x: is_pan_ready(self.text_agent, self.world),
                            "done",
                        ],  # make a BeefLettuce
                    ),
                    (
                        (
                            "BeefBurger",
                            lambda: is_ingredients_available(
                                self.text_agent, self.world, ["Lettuce"], ["done"]
                            ),  # other conditions except for available ingredients for making this burger
                        ),
                        [
                            "Beef",
                        ],
                        [
                            lambda x: is_pan_ready(self.text_agent, self.world),
                        ],
                    ),
                    (
                        "BeefLettuceBurger",
                        ["Beef", "LettuceBurger"],
                        [lambda x: is_pan_ready(self.text_agent, self.world), ""],
                    ),
                    (
                        "BeefLettuce",
                        ["Beef", "Lettuce"],
                        [
                            "done",
                            "done",
                        ],
                    ),  # make a BeefLettuce
                    ("BeefLettuceBurger", ["BeefLettuce"], [""]),
                    (
                        (
                            "BeefBurger",
                            lambda: is_ingredients_available(
                                self.text_agent, self.world, ["Lettuce"], ["done"]
                            ),  # other conditions except for available ingredients for making this burger
                        ),
                        [
                            "Beef",
                        ],
                        [
                            "done",
                        ],
                    ),
                    (
                        (
                            "LettuceBurger",
                            lambda: is_ingredients_available(
                                self.text_agent, self.world, ["Beef"], ["done"]
                            ),  # other conditions except for available ingredients for making this burger
                        ),
                        ["Lettuce"],
                        ["done"],
                    ),
                    ("BeefLettuceBurger", ["BeefBurger", "Lettuce"], ["", "done"]),
                    ("BeefLettuceBurger", ["Beef", "LettuceBurger"], ["done", ""]),
                ],
                (("BeefLettuce", ("Beef", "Lettuce")),): [("BeefLettuceBurger", ["BeefLettuce"], [""])],
                (
                    ("BeefLettuce", ("Beef", "Lettuce")),
                    ("BeefLettuceBurger", ("BeefLettuce",)),
                ): True,
                (("BeefBurger", ("Beef",)),): [("BeefLettuceBurger", ["BeefBurger", "Lettuce"], ["", "done"])],
                (
                    ("BeefBurger", ("Beef",)),
                    ("BeefLettuceBurger", ("BeefBurger", "Lettuce")),
                ): True,
                (("LettuceBurger", ("Lettuce",)),): [("BeefLettuceBurger", ["Beef", "LettuceBurger"], ["done", ""])],
                (
                    ("LettuceBurger", ("Lettuce",)),
                    ("BeefLettuceBurger", ("Beef", "LettuceBurger")),
                ): True,
                (("BeefLettuceBurger", ("BeefBurger", "Lettuce")),): True,
                (("BeefLettuceBurger", ("BeefLettuce",)),): True,
                (("BeefLettuceBurger", ("Beef", "LettuceBurger")),): True,
            },
        }
        self.food_ingredients_urgency = {
            "LettuceBurger": {},
            "BeefBurger": {},
            "BeefLettuce": {},
            "BeefLettuceBurger": {(): [1, 1, 1, 2, 2, 2, 2, 2, 2]},
        }
        self._assemble_process = {
            "LettuceBurger": {
                ("Lettuce",): [
                    [
                        (
                            "pickup_bread_in_plate",
                            lambda agent, world: is_ingredients_available(agent, world, ["Lettuce"], ["done"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done",
                    ],
                    [
                        (
                            "get_bread_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Lettuce"], ["in_plate"]),
                            (self.text_agent, self.world),
                        ),
                        "put_onto_plate_with_lettuce",
                    ],
                    [  # change to pickup bread
                        (
                            "get_bread_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Lettuce"], ["in_plate"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done",
                    ],
                    [
                        (
                            "pickup_lettuce_in_plate",
                            is_ingredients_available,
                            (
                                self.text_agent,
                                self.world,
                                ["Lettuce", "Bread"],
                                ["in_plate", ""],
                            ),
                        ),
                        "plate_bread",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Lettuce"], ["done"])
                            and not is_ingredients_available(agent, world, ["Lettuce"], ["in_plate"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done",
                        "plate_bread",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Lettuce"], ["done"])
                            and not is_ingredients_available(agent, world, ["Lettuce"], ["in_plate"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done",
                        (
                            "get_bread_from_station",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Lettuce"], ["in_plate"]),
                        ),
                        "put_onto_plate_with_lettuce",
                    ],
                    [  # change to pickup bread
                        (
                            "get_plate_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Lettuce"], ["in_plate"])
                            and not is_ingredients_available(agent, world, ["Lettuce"], ["in_plate"]),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done",
                        (
                            "get_bread_from_station",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Lettuce"], ["done"]),
                        ),
                        "plate_lettuce_done",
                    ],
                ],
            },
            "BeefBurger": {
                ("Beef",): [
                    [
                        (
                            "pickup_bread_in_plate",
                            is_closest_to_ready_pan,
                            (self.text_agent, self.world, "Bread", "in_plate"),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (
                                self.text_agent,
                                self.world,
                            ),
                        ),
                        "plate_beef_done_from_pan",
                        "plate_bread",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (
                                self.text_agent,
                                self.world,
                            ),
                        ),
                        "plate_beef_done_from_pan",
                        (
                            "get_bread_from_station",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Beef"], ["in_plate"]),
                        ),
                        "put_onto_plate_with_beef",
                    ],
                    [  # change to pickup
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (
                                self.text_agent,
                                self.world,
                            ),
                        ),
                        "plate_beef_done_from_pan",
                        (
                            "get_bread_from_station",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Beef"], ["in_plate"]),
                        ),
                        "plate_beef_done",
                    ],
                    [
                        (
                            "pickup_bread_in_plate",
                            lambda agent, world: not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done",
                    ],
                    [
                        (
                            "pickup_beef_done",
                            lambda agent, world, ingredients, status_list: is_ingredients_available(
                                agent, world, ingredients, status_list
                            )
                            and not is_pan_ready(agent, world),
                            (
                                self.text_agent,
                                self.world,
                                ["Beef", "Bread"],
                                ["in_plate", ""],
                            ),
                        ),
                        "plate_bread",
                    ],
                    [
                        (
                            "get_bread_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Beef"], ["in_plate"])
                            and not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "put_onto_plate_with_beef",
                    ],
                    [
                        (
                            "get_bread_from_station",
                            lambda agent, world: is_ingredients_available(agent, world, ["Beef"], ["in_plate"])
                            and not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done",
                    ],
                ]
            },
            "BeefLettuce": {
                ("Beef", "Lettuce"): [
                    [
                        (
                            "pickup_lettuce_in_plate",
                            is_closest_to_ready_pan,
                            (self.text_agent, self.world, "Lettuce", "in_plate"),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (self.text_agent, self.world),
                        ),
                        (
                            "plate_beef_done_from_pan",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Lettuce"], ["done"]),
                        ),
                        "plate_lettuce_done",
                    ],
                    [
                        (
                            "pickup_lettuce_in_plate",
                            lambda agent, world: not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done",
                    ],
                    [
                        (
                            "pickup_beef_done",
                            lambda agent, world: not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuce_done",
                    ],
                ],
            },
            "BeefLettuceBurger": {
                ("Beef", "LettuceBurger"): [
                    [
                        (
                            "pickup_lettuceburger",
                            is_closest_to_ready_pan,
                            (self.text_agent, self.world, "LettuceBurger", ""),
                        ),
                        "plate_beef_done_from_pan",
                    ],
                    [
                        (
                            "get_plate_from_station",
                            is_pan_ready,
                            (self.text_agent, self.world),
                        ),
                        (
                            "plate_beef_done_from_pan",
                            is_ingredients_available,
                            (agent, world, ["LettuceBurger"], [""]),
                        ),
                        "plate_lettuceburger",
                    ],
                    [
                        (
                            "pickup_lettuceburger",
                            lambda agent, world: not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_beef_done",
                    ],
                    [
                        (
                            "pickup_beef_done",
                            lambda agent, world: not is_pan_ready(agent, world),
                            (self.text_agent, self.world),
                        ),
                        "plate_lettuceburger",
                    ],
                ],
                ("BeefLettuce",): [
                    [
                        "get_bread_from_station",
                        "put_onto_plate_with_beeflettuce",
                    ],
                    [
                        "get_bread_from_station",
                        "plate_beeflettuce",
                    ],  # change to pickup
                    [
                        (
                            "pickup_beeflettuce",
                            is_ingredients_available,
                            (self.text_agent, self.world, ["Bread"], [""]),
                        ),
                        "plate_bread",
                    ],
                ],
                ("BeefBurger", "Lettuce"): [
                    ["pickup_beefburger", "plate_lettuce_done"],
                ],
            },
        }

        assert self._check_process(self._assemble_process)
        for burger, ingredients_dict in self._num_assemble_process.items():
            for ingredient, num in ingredients_dict.items():
                assert (
                    len(self._assemble_process[burger][ingredient]) == num
                ), f"num error in processes for assemble {burger} using {ingredient}"
        self._assemble_process_forward_index = self._processes_transform(self._assemble_process)
        logger.trace("\n" + pretty_repr(self._assemble_process_forward_index))
        logger.trace("\n" + pretty_repr(self.food_ingredients_index))

        self._pass_on_process_forward_index = {}
        self._serve_process_forward_index = {}
        self._putout_fire_forward_index = {}
        self._clean_a_counter_forward_index = {}

        # with open("examples/mid_valid_actions.json", "w", encoding="utf-8") as f:
        #     json.dump(self.valid_actions, f)

    def update(self, agent: TextAgent, world: CookingWorld):
        self.text_agent = agent
        self.agent = agent.agent
        self.agent_idx = self.text_agent.agent_idx
        self.world = world

    def reset(self):
        self.prev_subtasks: List[str] = []
        self.prev_task: tuple = None
        self._assemble_prev_recipes: List[Tuple[str]] = []

    def get_valid_mid_actions(self):
        _valid_actions = {
            "prepare": [],
            "assemble": [],
            "pass_on": [],
            "serve": [],
            "putout_fire": [],
            "clean_a_counter": [],
        }
        if self.prev_subtasks or self.prev_task or self._assemble_prev_recipes:
            logger.warning(f"Not empty running memory")
            self.reset()
        for action in self.valid_actions:
            for params in self.valid_actions[action]:
                end, _ = getattr(self, action)(**params, prev_subtask_succeeded=False)
                self.reset()
                if not end:
                    _valid_actions[action].append(params)
        return _valid_actions

    def _check_process(self, process: Union[Dict, List]) -> bool:
        """
        Check whether the process is legal.
        """
        if isinstance(process, dict):
            for target, target_iter in process.items():
                if isinstance(target_iter, dict):
                    if not self._check_process(target_iter):
                        logger.warning(f"Check process {target} failed!")
                        return False
                elif isinstance(target_iter, list):
                    if not self._check_process(target_iter):
                        logger.warning(f"Check process {target} failed!")
                        return False
                else:
                    raise NotImplementedError(target_iter)

        else:  # list
            for target in process:
                if isinstance(target, list):
                    if not self._check_process(target):
                        return False
                elif isinstance(target, tuple):
                    if target[0] not in TextAgent.legal_text_actions:
                        logger.warning(f"{target[0]} is invalid")
                        return False
                    if not (isinstance(target[1], Callable) or target[1] is None):
                        logger.warning(f"{target[1]} is invalid for {target[0]}")
                        return False
                elif isinstance(target, str):  # str
                    if target not in TextAgent.legal_text_actions:
                        logger.warning(f"{target} is invalid")
                        return False
                else:
                    raise NotImplementedError(target)

        return True

    def _processes_transform(self, process) -> Dict:
        """
        Generate:
        - A forward index dict (previous subtasks -> possible next subtasks) for each process
        """
        forward_index = {}
        for task, _p in process.items():
            if isinstance(_p, dict):
                forward_index[task] = self._processes_transform(_p)
            elif isinstance(_p, list):
                _index = {}
                for _sp in _p:
                    subtasks = []
                    for i, _st in enumerate(_sp):
                        # logger.trace(_index)
                        if isinstance(_st, str):
                            current_subtask = _st
                            if i == 0:
                                _index[tuple(subtasks)] = _index.get(tuple(subtasks), []) + [(current_subtask, None)]
                        else:
                            current_subtask = _st[0]
                            if i == 0:
                                _index[tuple(subtasks)] = _index.get(tuple(subtasks), []) + [_st]
                        subtasks.append(current_subtask)
                        if i == len(_sp) - 1:
                            _index[tuple(subtasks)] = True
                            continue
                        if isinstance(_sp[i + 1], str):
                            next_subtask = (_sp[i + 1], None)
                        else:
                            next_subtask = _sp[i + 1]
                        _index[tuple(subtasks)] = _index.get(tuple(subtasks), []) + [next_subtask]
                forward_index[task] = _index
        return forward_index

    def _get_or_pickup(self, subtask: str, target: str, target_status: Union[str, Callable] = "") -> str:
        """
        Get an ingredient from the station or pickup it from the counter.
        """
        # MARK: do not transform
        #   - prepare bread
        assert "from_station" in subtask, subtask
        target_station = target
        target = target[:-7]
        assert target in ["Lettuce", "Beef", "Bread", "Plate"]

        def check(x) -> bool:
            if len(self.world.get_objects_at(x.location, Counter)) != 1:
                return False
            elif target not in ["Plate"] and not (
                self.text_agent.is_target_status(x, target_status)
                if isinstance(target_status, str)
                else target_status(x)
            ):
                return False
            elif isinstance(x, Plate):
                return len(x.content) == 0 and (isinstance(target_status, str) or target_status(x))
            elif isinstance(x, Bread):
                return True
            else:
                return self.text_agent.is_target_status(x, "fresh")

        targets_on_counter = self.text_agent.get_objects(
            target,
            check=check,
        )
        stations = self.text_agent.get_objects(target_station)
        if (
            len(targets_on_counter) > 0
            and self.text_agent.closest(targets_on_counter)[1] < self.text_agent.closest(stations)[1]
        ):
            self.text_agent.assigned_target = self.text_agent.closest(targets_on_counter)[0]
            if target in ["Lettuce", "Beef"]:
                return f"pickup_{target.lower()}_fresh"
            else:
                return f"pickup_{target.lower()}"
        return subtask

    # MARK: agent will complete the task at all cases
    def prepare(self, food: str, plate: bool = None, prev_subtask_succeeded: bool = True) -> Tuple[bool, str]:
        """
        Prepare an food, available foods are: Lettuce, Beef, Bread.

        Parameters
        `food` | str: The food to prepare.
            - Lettuce: Pickup a Lettuce from the LettuceStation or the Counter, put it onto the CutBoard, then chop it. The Lettuce will be put on a plate which is pickup from the PlateStation or the Counter if `plate` is True else will be left on the CutBoard.
            - Beef: Get a Beef from the BeefStation or the Counter, put it onto the Pan, the Beef will be ready after 30 steps. The Beef will be put on a plate which is pickup from the PlateStation or the Counter if `plate` is True else will be burned after 40 steps.
            - Bread: If `plate` is True, get a Plate from the PlateStation and put it onto the Counter if there is not a Plate on the Counter, get a Bread from the BreadStation and put it onto the Plate. Else, get a Bread from the BreadStation and put it onto the Counter.

        `plate` | bool: Whether to put the food on a plate. Default: True.

        Return
            (Whether the task ends, the next subtask if the task does not end else the task status)
        """
        assert food in ["Lettuce", "Beef", "Bread"], food
        if plate is None and food in ["Beef"]:
            plate = True
        elif plate is None:
            plate = False
        n_try = 0
        status = ""
        end = False
        current_subtask = None
        logger.debug(f"prepare {food} plate = {plate}")
        logger.debug(f"traj {self.prev_subtasks}")
        if not prev_subtask_succeeded and len(self.prev_subtasks) > 0:
            self.prev_subtasks.pop()
            logger.trace(f"previous subtask failed, traj: {self.prev_subtasks}")

        if self.prev_task != ("prepare", food, plate):
            if tuple(self.prev_subtasks) not in self._prepare_process_forward_index[food][plate]:
                self.prev_subtasks = []
            self.prev_task = ("prepare", food, plate)
        valid_actions = self.text_agent.get_valid_actions()

        while current_subtask is None:
            n_try += 1
            next_subtask_cands = self._prepare_process_forward_index[food][plate][tuple(self.prev_subtasks)]
            if next_subtask_cands is True:
                current_subtask = True
                break
            possible_cands = []
            for n_st in next_subtask_cands:
                logger.trace(f"n_st {n_st}")
                if n_st[0] in valid_actions and (n_st[1] is None or n_st[1](*n_st[2])):
                    logger.trace(f"{n_st[0]} valid")
                    possible_cands.append(n_st)
                    # current_subtask = n_st[0]
                    # break
            if len(possible_cands) > 0:
                current_subtask = random.choice(possible_cands)[0]
            if current_subtask is None:
                if len(self.prev_subtasks) > 0:
                    trace_back_subtask = self.prev_subtasks.pop()
                    logger.trace(f"trace_back {trace_back_subtask}, traj {self.prev_subtasks}")
                else:
                    break
            logger.trace(f"n_try {n_try}, current_subtask {current_subtask}")
            if n_try >= self.max_n_try:
                logger.warning(f"try more than {self.max_n_try} times")
                break

        if current_subtask is None:
            logger.warning(f"Cannot prepare {food}!")
            end = True
            status = f"Failed, you can not prepare {food} and should expect that your partner pass on the {food} to the counter and pick it up, or you can try again"
        elif current_subtask is True:
            end = True
            status = "Succeeded"
        else:
            end = False
            status = current_subtask

        if end:
            self.prev_subtasks = []
            self.prev_task = None
        else:
            self.prev_subtasks.append(current_subtask)
            if food in ["Lettuce", "Beef"] and "from_station" in current_subtask:
                status = self._get_or_pickup(
                    current_subtask,
                    *self.text_agent.get_instruction(current_subtask)[1],
                )

        # assert (not end and status in valid_actions) or status.startswith("Succeeded") or status.startswith("Failed"), (
        #     end,
        #     status,
        # )
        return (end, status)

    def assemble(self, food: str, prev_subtask_succeeded: bool = True) -> Tuple[bool, str]:
        """
        Assemble a burger, available burgers are: LettuceBurger, BeefBurger, BeefLettuceBurger, which are made of different ingredients.
        Except for Bread, all other ingredients should be prepared first. For example, you can assemble a BeefBurger when only a Beef is prepared.
        Parameters
        `burger` | str: The burger to assemble.
            - LettuceBurger: A LettuceBurger is made of a Lettuce and a Bread.
            - BeefBurger: A BeefBurger is made of a Beef and a Bread.
            - BeefLettuce: A BeefLettuce is made of a Beef and a Lettuce.
            - BeefLettuceBurger: A BeefLettuceBurger can be made in different ways:
                1. A Beef, a Lettuce and a Bread.
                2. A BeefLettuce and a Bread.
                3. A BeefBurger and a Lettuce.
                4. A LettuceBurger and a Beef.
        All the burgers will be assembled on a plate.
        """
        # DEV
        # first transform put_onto to plate then check whether it is in valid actions
        # transform get from_station can be done at the end
        assert food in [
            "LettuceBurger",
            "BeefBurger",
            "BeefLettuce",
            "BeefLettuceBurger",
        ]
        n_try = 0

        def is_ingredients_recipe_valid(
            food: Tuple[Union[str, Tuple[str, Callable]]],
            ingredient_list: List[str],
            ingredient_status_list: List[Union[str, Callable]],
        ) -> bool:
            food_status = food[1] if isinstance(food, tuple) else lambda: True
            food = food[0] if isinstance(food, tuple) else food
            if (
                is_ingredients_available(
                    self.text_agent,
                    self.world,
                    ingredient_list,
                    ingredient_status_list,
                )
                and food_status()
            ):
                return True
            return False

        status = ""
        end = False
        current_subtask = None
        logger.trace(f"assemble {food}")
        logger.trace(f"recipes {self._assemble_prev_recipes}")
        logger.trace(f"traj {self.prev_subtasks}")
        if not prev_subtask_succeeded:
            self.prev_subtasks.pop()
            logger.trace(f"previous subtask failed, traj: {self.prev_subtasks}")

        valid_actions = self.text_agent.get_valid_actions()

        if len(self._assemble_prev_recipes) > 0:
            sub_food = self._assemble_prev_recipes[-1][0]
            ingredient_tuple = self._assemble_prev_recipes[-1][1]
            if self.prev_task != ("assemble", food, sub_food, ingredient_tuple):
                while (
                    tuple(self._assemble_prev_recipes) not in self.food_ingredients_index[food]
                    and len(self._assemble_prev_recipes) > 0
                ):
                    logger.trace(f"task changed! trace_back {self._assemble_prev_recipes[-1]}")
                    self._assemble_prev_recipes.pop()
            logger.trace(f"current recipes {self._assemble_prev_recipes}")

        if len(self._assemble_prev_recipes) == 0:
            ingredients_cands = self.food_ingredients_index[food][tuple(self._assemble_prev_recipes)]
            ingredients_urgency = self.food_ingredients_urgency[food].get(
                tuple(self._assemble_prev_recipes), [1] * len(ingredients_cands)
            )
            assert len(ingredients_cands) == len(ingredients_urgency)
            urgency_to_ingredients_cands = defaultdict(list)
            for (sub_food, ingredient_list, ingredient_status_list), urgency in zip(
                ingredients_cands, ingredients_urgency
            ):
                if is_ingredients_recipe_valid(sub_food, ingredient_list, ingredient_status_list):
                    sub_food = sub_food[0] if isinstance(sub_food, tuple) else sub_food
                    urgency_to_ingredients_cands[urgency].append((sub_food, tuple(ingredient_list)))
            if len(urgency_to_ingredients_cands) == 0:
                sub_food = ""
                ingredient_list = []
            else:
                highest_urgency = min(urgency_to_ingredients_cands.keys())
                logger.trace(f"highest_urgency {highest_urgency} for {food}, cands {urgency_to_ingredients_cands}")
                cand = random.choice(urgency_to_ingredients_cands[highest_urgency])
                sub_food, ingredient_list = cand[:2]
                self._assemble_prev_recipes.append((sub_food, tuple(ingredient_list)))

            if len(ingredient_list) == 0:
                end = True
                logger.warning(f"Cannot assemble {food}, lack of ingredients!")
                status = f"Failed, lack of necessary ingredients to assemble {food}, check the needed ingredients, prepare the ingredients and try again"

        while len(self._assemble_prev_recipes) > 0:
            sub_food = self._assemble_prev_recipes[-1][0]
            ingredient_tuple = self._assemble_prev_recipes[-1][1]
            if self.prev_task != ("assemble", food, sub_food, ingredient_tuple):
                if tuple(self.prev_subtasks) not in self._assemble_process_forward_index[sub_food][ingredient_tuple]:
                    self.prev_subtasks = []
                self.prev_task = ("assemble", food, sub_food, ingredient_tuple)
                logger.trace(
                    f"assemble {food} through making {self._assemble_prev_recipes[-1][0],self._assemble_prev_recipes[-1][1]}"
                )
                logger.trace(f"recipes {self._assemble_prev_recipes}")
                logger.trace(f"traj {self.prev_subtasks}")

            while current_subtask is None:
                logger.trace(f"n_try {n_try}")
                n_try += 1
                next_subtask_cands = self._assemble_process_forward_index[sub_food][ingredient_tuple][
                    tuple(self.prev_subtasks)
                ]
                if next_subtask_cands is True:
                    logger.debug(f"sub_food {sub_food} is done")
                    current_subtask = True
                    break
                # MARK: trace back recipes
                if len(self.prev_subtasks) == 0:
                    ingredients_cands = self.food_ingredients_index[food][tuple(self._assemble_prev_recipes[:-1])]
                    for (
                        sub_food,
                        ingredient_list,
                        ingredient_status_list,
                    ) in ingredients_cands:
                        _sub_food_name = sub_food[0] if isinstance(sub_food, tuple) else sub_food
                        if _sub_food_name == self._assemble_prev_recipes[-1][0] and ingredient_list == list(
                            self._assemble_prev_recipes[-1][1]
                        ):
                            logger.debug(f"{sub_food} {ingredient_list} {ingredient_status_list}")
                            if is_ingredients_recipe_valid(sub_food, ingredient_list, ingredient_status_list):
                                logger.debug(f"{sub_food} {ingredient_list} {ingredient_status_list} valid")
                                break
                    else:
                        logger.debug(f"no valid recipe for sub_food {self._assemble_prev_recipes[-1]}")
                        break
                possible_cands = []
                for n_st in next_subtask_cands:
                    logger.trace(f"n_st {n_st}")
                    if n_st[0] in valid_actions and (n_st[1] is None or n_st[1](*n_st[2])):
                        logger.trace(f"n_st {n_st} valid")
                        possible_cands.append(n_st)
                        # current_subtask = n_st[0]
                        # break
                if len(possible_cands) > 0:
                    current_subtask = random.choice(possible_cands)[0]
                if current_subtask is None:
                    if len(self.prev_subtasks) > 0:
                        trace_back_subtask = self.prev_subtasks.pop()
                        logger.trace(f"trace_back {trace_back_subtask}, traj {self.prev_subtasks}")
                    else:
                        logger.trace(f"can not trace_back traj {self.prev_subtasks}, try changing ingredients")
                        break
                logger.trace(f"n_try {n_try}, current_subtask {current_subtask}")
                if n_try >= self.max_n_try:
                    logger.warning(f"try more than {self.max_n_try} times")
                    break
            if n_try >= self.max_n_try:
                logger.warning(f"try more than {self.max_n_try} times")
                break
            if current_subtask is None or current_subtask is True:
                trace_back_recipe = None
                if current_subtask is None:
                    trace_back_recipe = self._assemble_prev_recipes.pop()
                    logger.warning(
                        f"current sub_food invalid, trace_back recipe {trace_back_recipe}, recipes {self._assemble_prev_recipes}"
                    )
                ingredients_cands = self.food_ingredients_index[food][tuple(self._assemble_prev_recipes)]
                if ingredients_cands is True:
                    assert current_subtask is True  # burger is assembled
                    logger.debug(f"food {food} is assembled")
                    break
                current_subtask = None  # reset current_subtask for next sub_food
                ingredients_urgency = self.food_ingredients_urgency[food].get(
                    tuple(self._assemble_prev_recipes), [1] * len(ingredients_cands)
                )
                urgency_to_ingredients_cands = defaultdict(list)
                for (
                    sub_food,
                    ingredient_list,
                    ingredient_status_list,
                ), urgency in zip(ingredients_cands, ingredients_urgency):
                    if is_ingredients_recipe_valid(sub_food, ingredient_list, ingredient_status_list):
                        sub_food = sub_food[0] if isinstance(sub_food, tuple) else sub_food
                        urgency_to_ingredients_cands[urgency].append((sub_food, tuple(ingredient_list)))
                if len(urgency_to_ingredients_cands) > 0:
                    highest_urgency = min(urgency_to_ingredients_cands.keys())
                    logger.trace(f"highest_urgency {highest_urgency} for {food}, cands {urgency_to_ingredients_cands}")
                    cand = random.choice(urgency_to_ingredients_cands[highest_urgency])
                    sub_food, ingredient_list = cand[:2]
                    if (sub_food, ingredient_list) != trace_back_recipe:
                        self._assemble_prev_recipes.append((sub_food, tuple(ingredient_list)))
                elif len(self._assemble_prev_recipes) > 0:
                    trace_back_recipe = self._assemble_prev_recipes.pop()
                    logger.warning(
                        f"no next sub_food recipe, trace_back recipe {trace_back_recipe}, recipes {self._assemble_prev_recipes}"
                    )
            else:
                break

        if current_subtask is None:
            logger.warning(f"Cannot assemble {food}!")
            end = True
            if status == "":
                status = f"Failed, lack of necessary ingredients to assemble {food} (ingredients may be used by your partner), check the needed ingredients, prepare the ingredients and try again"
        elif current_subtask is True:
            end = True
            status = "Succeeded"
        else:
            end = False
            status = current_subtask

        if end:
            self.prev_task = None
            self.prev_subtasks = []
            self._assemble_prev_recipes = []
        else:
            self.prev_subtasks.append(current_subtask)
            if "from_station" in current_subtask:
                status = self._get_or_pickup(
                    current_subtask,
                    *self.text_agent.get_instruction(current_subtask)[1],
                )
        # assert (not end and status in valid_actions) or status.startswith("Succeeded") or status.startswith("Failed"), (
        #     end,
        #     status,
        # )
        return (end, status)

    def pass_on(self, thing: str, thing_status: str = "", prev_subtask_succeeded: bool = True) -> Tuple[bool, str]:
        n_try = 0
        status = ""
        end = False
        current_subtask = None
        well_desc_to_code_pairs = {
            ("Lettuce", "Chopped"): ("Lettuce", "done"),
            ("Lettuce", "Unchopped"): ("Lettuce", "fresh"),
            ("Beef", "Well-cooked"): ("Beef", "done"),
            ("Beef", "Fresh"): ("Beef", "fresh"),
        }
        if (thing, thing_status) in well_desc_to_code_pairs:
            thing, thing_status = well_desc_to_code_pairs[(thing, thing_status)]
        assert (thing, thing_status) in self.text_agent.legal_pickup_targets
        logger.trace(f"traj {self.prev_subtasks}")
        # assert self.world == self.text_agent.world, (self.world, self.text_agent.world)
        # logger.debug(self.world.world_objects["Lettuce"])
        # logger.debug(self.text_agent.get_objects("Lettuce"))
        from_station_tuples = [
            ("Lettuce", "fresh"),
            ("Beef", "fresh"),
            ("Bread", ""),
            ("Plate", ""),
        ]

        def in_center_counter(x: Object):
            counter_objects = self.world.get_objects_at(x.location, Counter)
            return len(counter_objects) == 1 and self.text_agent.is_target_status(counter_objects[0], "center")

        def is_valid_center_counter(x: Object):
            if (thing, thing_status) in [("Lettuce", "done"), ("Bread", "")]:
                plate_objects = self.world.get_objects_at(x.location, Plate)
                if len(plate_objects) > 0:
                    return self.text_agent.is_target_status(x, "center") and len(plate_objects[0].content) == 0
            return self.text_agent.is_target_status(x, "center") and (len(self.world.get_objects_at(x.location)) == 1)

        if (thing, thing_status) not in self._pass_on_process_forward_index:
            if (thing, thing_status) in from_station_tuples:
                pass_on_subtasks = [
                    [
                        (
                            "get_" + thing.lower() + "_from_station",
                            lambda agent, world: is_ingredients_available(
                                agent,
                                world,
                                ["Counter"],
                                [is_valid_center_counter],
                            ),
                            (self.text_agent, self.world),
                        ),
                        "put_onto_center_counter",
                    ]
                ]
            elif (thing, thing_status) in [("Beef", "done"), ("Beef", "overcooked")]:
                pass_on_subtasks = [
                    [
                        (
                            "get_plate_from_station",
                            is_ingredients_available,
                            (
                                self.text_agent,
                                self.world,
                                [thing, "Counter"],
                                [
                                    lambda x: self.text_agent.is_target_status(x, thing_status)
                                    and len(self.world.get_objects_at(x.location, Pan)) == 1,
                                    is_valid_center_counter,
                                ],
                            ),
                        ),
                        "plate_" + thing.lower() + "_" + thing_status + "_from_pan",
                        "put_onto_center_counter",
                    ],
                    [
                        (
                            "pickup_" + CapToText[thing] + "_" + thing_status,
                            lambda: is_ingredients_available(
                                self.text_agent,
                                self.world,
                                ["Counter", thing],
                                [
                                    is_valid_center_counter,
                                    lambda x: self.text_agent.is_target_status(x, thing_status)
                                    and not in_center_counter(x),
                                ],
                            ),
                            (),
                        ),
                        "put_onto_center_counter",
                    ],
                ]
            else:
                pass_on_subtasks = [
                    [
                        (
                            (
                                ("pickup_" + CapToText[thing] + "_" + thing_status)
                                if thing_status != ""
                                else "pickup_" + CapToText[thing]
                            ),
                            lambda: is_ingredients_available(
                                self.text_agent,
                                self.world,
                                ["Counter", thing],
                                [
                                    is_valid_center_counter,
                                    lambda x: self.text_agent.is_target_status(x, thing_status)
                                    and not in_center_counter(x),
                                ],
                            ),
                            (),
                        ),
                        "put_onto_center_counter",
                    ]
                ]

            if (thing, thing_status) in [("Lettuce", "done"), ("Bread", "")]:
                pass_on_subtasks.insert(0, [*pass_on_subtasks[-1][:-1], "put_onto_plate"])

            pass_on_subtasks = {(thing, thing_status): pass_on_subtasks}
            assert self._check_process(pass_on_subtasks)
            self._pass_on_process_forward_index = self._processes_transform(pass_on_subtasks)

            logger.debug(
                f"pass_on {thing} {thing_status} forward index:\n {pretty_repr(self._pass_on_process_forward_index)}"
            )

        if not prev_subtask_succeeded and len(self.prev_subtasks) > 0:
            self.prev_subtasks.pop()
            logger.trace(f"previous subtask failed, traj: {self.prev_subtasks}")

        if self.prev_task != ("pass_on", thing, thing_status):
            if tuple(self.prev_subtasks) not in self._pass_on_process_forward_index:
                self.prev_subtasks = []
            self.prev_task = ("pass_on", thing, thing_status)
        valid_actions = self.text_agent.get_valid_actions()
        while current_subtask is None:
            n_try += 1
            next_subtask_cands = self._pass_on_process_forward_index[(thing, thing_status)][tuple(self.prev_subtasks)]
            if next_subtask_cands is True:
                current_subtask = True
                break
            else:
                for n_t in next_subtask_cands:
                    next_subtask = n_t[0]
                    next_subtask_cond = n_t[1] is None or n_t[1](*n_t[2])
                    if next_subtask in valid_actions and next_subtask_cond:
                        current_subtask = next_subtask
                        break
            if current_subtask is None:
                if len(self.prev_subtasks) > 0:
                    trace_back_subtask = self.prev_subtasks.pop()
                    logger.trace(f"trace_back {trace_back_subtask}, traj {self.prev_subtasks}")
                else:
                    break
            logger.trace(f"n_try {n_try}, current_subtask {current_subtask}")
            if n_try >= self.max_n_try:
                logger.warning(f"try more than {self.max_n_try} times")
                break
        if current_subtask is None:
            logger.warning(f"Cannot pass on {thing}!")
            end = True
            if status == "":
                if not is_ingredients_available(
                    self.text_agent,
                    self.world,
                    ["Counter"],
                    [
                        lambda x: self.text_agent.is_target_status(x, "center")
                        and len(self.world.get_objects_at(x.location)) == 1,
                    ],
                ):
                    status = "Failed: no idle counter, clean a counter first"
                elif thing_status == "":
                    status = "Failed: no such thing: " + thing
                else:
                    status = f"Failed: no such thing: {thing} with status {thing_status}"
        elif current_subtask is True:
            end = True
            status = "Succeeded"
        else:
            end = False
            status = current_subtask

        if end:
            self.prev_task = None
            self.prev_subtasks = []
        else:
            self.prev_subtasks.append(current_subtask)
            if "from_station" in current_subtask:
                status = self._get_or_pickup(
                    current_subtask,
                    self.text_agent.get_instruction(current_subtask)[1][0],
                    lambda x: not in_center_counter(x),
                )
            if "put_onto" in current_subtask and "plate" in current_subtask:

                def check_plate(x: Object) -> bool:
                    if len(x.content) > 0:
                        return False
                    counter = self.world.get_objects_at(x.location, Counter)
                    if len(counter) > 0:
                        counter = counter[0]
                        if "center" in status:
                            return self.text_agent.is_target_status(counter, "center")
                        elif "edge" in status:
                            return self.text_agent.is_target_status(counter, "edge")
                        return True
                    return False

                plate_objects = self.text_agent.get_objects("Plate", check=check_plate)
                self.text_agent.assigned_target = self.text_agent.closest(plate_objects)[0]
            if "pickup" in current_subtask:
                _, (target, target_status) = self.text_agent.get_instruction(current_subtask)
                target_objects = self.text_agent.get_objects(
                    target,
                    check=lambda x: self.text_agent.is_target_status(x, target_status) and not in_center_counter(x),
                )
                self.text_agent.assigned_target = self.text_agent.closest(target_objects)[0]
        return (end, status)

    def serve(self, food: str, prev_subtask_succeeded: bool = True) -> Tuple[bool, str]:
        n_try = 0
        status = ""
        end = False
        current_subtask = None
        logger.trace(f"traj {self.prev_subtasks}")
        legal_foods = ["BeefBurger", "LettuceBurger", "BeefLettuceBurger"]
        assert food in legal_foods, food

        if food not in self._serve_process_forward_index:
            serve_subtasks = [["pickup_" + CapToText[food], "deliver"]]
            serve_subtasks = {food: serve_subtasks}

            assert self._check_process(serve_subtasks)
            self._serve_process_forward_index = self._processes_transform(serve_subtasks)
            logger.debug(f"serve {food} forward index:\n {pretty_repr(self._serve_process_forward_index)}")

        if not prev_subtask_succeeded and len(self.prev_subtasks) > 0:
            self.prev_subtasks.pop()
            logger.trace(f"previous subtask failed, traj: {self.prev_subtasks}")

        if self.prev_task != ("serve", food):
            if tuple(self.prev_subtasks) not in self._serve_process_forward_index[food]:
                self.prev_subtasks = []
            self.prev_task = ("serve", food)

        valid_actions = self.text_agent.get_valid_actions()

        while current_subtask is None:
            n_try += 1
            next_subtask_cands = self._serve_process_forward_index[food][tuple(self.prev_subtasks)]
            if next_subtask_cands is True:
                current_subtask = True
                break
            else:
                for n_t in next_subtask_cands:
                    next_subtask = n_t[0]
                    next_subtask_cond = n_t[1] is None or n_t[1](*n_t[2])
                    if next_subtask in valid_actions and next_subtask_cond:
                        current_subtask = next_subtask
                        break
            if current_subtask is None:
                if len(self.prev_subtasks) > 0:
                    trace_back_subtask = self.prev_subtasks.pop()
                    logger.trace(f"trace_back {trace_back_subtask}, traj {self.prev_subtasks}")
                else:
                    break
            logger.trace(f"n_try {n_try}, current_subtask {current_subtask}")
            if n_try >= self.max_n_try:
                logger.warning(f"try more than {self.max_n_try} times")
                break
        if current_subtask is None:
            logger.warning(f"Cannot serve {food}!")
            end = True
            status = f"Failed: no {food} on counter, prepare ingredients and assemble a {food} and try again"
        elif current_subtask is True:
            end = True
            status = "Succeeded"
        else:
            end = False
            status = current_subtask

        if end:
            self.prev_task = None
            self.prev_subtasks = []
        else:
            self.prev_subtasks.append(current_subtask)

        return (end, status)

    def putout_fire(self, prev_subtask_succeeded: bool = True) -> Tuple[bool, str]:
        n_try = 0
        status = ""
        end = False
        current_subtask = None
        logger.trace(f"traj {self.prev_subtasks}")

        if "fire" not in self._putout_fire_forward_index:
            putout_fire_subtasks = [
                [
                    ("pickup_fireextinguisher", is_on_fire, (self.text_agent, self.world)),
                    "put_out_fire",
                ]
            ]
            putout_fire_subtasks = {"fire": putout_fire_subtasks}
            assert self._check_process(putout_fire_subtasks)
            self._putout_fire_forward_index = self._processes_transform(putout_fire_subtasks)
            logger.debug(f"putout fire forward index:\n {pretty_repr(self._serve_process_forward_index)}")

        if not prev_subtask_succeeded and len(self.prev_subtasks) > 0:
            self.prev_subtasks.pop()
            logger.trace(f"previous subtask failed, traj: {self.prev_subtasks}")

        if self.prev_task != ("putout_fire",):
            if tuple(self.prev_subtasks) not in self._putout_fire_forward_index["fire"]:
                self.prev_subtasks = []
            self.prev_task = ("putout_fire",)
        valid_actions = self.text_agent.get_valid_actions()

        while current_subtask is None:
            n_try += 1
            next_subtask_cands = self._putout_fire_forward_index["fire"][tuple(self.prev_subtasks)]
            if next_subtask_cands is True:
                current_subtask = True
                break
            else:
                for n_t in next_subtask_cands:
                    next_subtask = n_t[0]
                    next_subtask_cond = n_t[1] is None or n_t[1](*n_t[2])
                    if next_subtask in valid_actions and next_subtask_cond:
                        current_subtask = next_subtask
                        break
            if current_subtask is None:
                if len(self.prev_subtasks) > 0:
                    trace_back_subtask = self.prev_subtasks.pop()
                    logger.trace(f"trace_back {trace_back_subtask}, traj {self.prev_subtasks}")
                else:
                    break
            logger.trace(f"n_try {n_try}, current_subtask {current_subtask}")
            if n_try >= self.max_n_try:
                logger.warning(f"try more than {self.max_n_try} times")
                break
        if current_subtask is None:
            logger.warning("Cannot put out fire!")
            end = True
            if is_on_fire(self.text_agent, self.world):
                status = "Failed: fire extinguisher is held by your partner, you can continue to fulfill orders"
            else:
                status = "Failed: no pan is on fire, you should continue to fulfill orders"
        elif current_subtask is True:
            end = True
            status = "Succeeded"
        else:
            end = False
            status = current_subtask

        if end:
            self.prev_task = None
            self.prev_subtasks = []
        else:
            self.prev_subtasks.append(current_subtask)

        return (end, status)

    def clean_a_counter(self, center: bool = False, prev_subtask_succeeded: bool = True) -> Tuple[bool, str]:
        """
        The agent will drop an overcooked beef if it exists, or randomly drop a food
        """
        n_try = 0
        end = False
        status = ""
        current_subtask = None
        logger.trace(f"traj {self.prev_subtasks}")

        occupy_counter_list = get_occupy_counter(self.text_agent, self.world)
        if center:
            occupy_counter_list = [x for x in occupy_counter_list if self.text_agent.is_target_status(x, "center")]
        occupy_objects = [self.world.get_objects_at(x.location, DynamicObject) for x in occupy_counter_list]
        occupy_objects = sum(occupy_objects, [])
        occupy_object_status_list = [
            (x, self.text_agent.get_dynamic_target_status(x))
            for x in occupy_objects
            if not isinstance(x, (FireExtinguisher,)) or (isinstance(x, Plate) and len(x.content) == 0)
        ]
        occupy_obj_sta_no_plate = [o_s for o_s in occupy_object_status_list if not isinstance(o_s[0], Plate)]

        prior_to_clean = [
            (bf, "overcooked")
            for bf in occupy_objects
            if isinstance(bf, Beef) and self.text_agent.is_target_status(bf, "overcooked")
        ]
        status_to_clean_priority = {
            "Beef": ["overcooked", "fresh", "done"],
            "Lettuce": ["fresh", "done"],
        }

        if not prev_subtask_succeeded and len(self.prev_subtasks) > 0:
            self.prev_subtasks.pop()
            logger.trace(f"previous subtask failed, traj: {self.prev_subtasks}")

        if self.prev_task is None or self.prev_task[0] != "clean_a_counter":
            if tuple(self.prev_subtasks) not in self._clean_a_counter_forward_index:
                self.prev_subtasks = []
            self.prev_task = None

        if (
            self.prev_task is None
            or self.prev_task[1] != center
            or (self.prev_task[3] not in occupy_object_status_list and len(self.prev_subtasks) == 0)
        ):
            if len(occupy_obj_sta_no_plate) > 0 or (len(occupy_object_status_list) > 0 and center):
                # transmit a plate from center to edge in the latter case
                # pick up the object with the highest priority to clean
                obj_sta = None
                for o_s in prior_to_clean:
                    if o_s in occupy_object_status_list:
                        obj_sta = o_s
                        break
                if obj_sta is None:
                    if len(occupy_obj_sta_no_plate) > 0:
                        o, s = random.choice(occupy_obj_sta_no_plate)
                    else:
                        o, s = random.choice(occupy_object_status_list)
                    o_class_str = type(o).__name__
                    if o_class_str in status_to_clean_priority:
                        for _s in status_to_clean_priority[o_class_str]:
                            if (o, _s) in occupy_object_status_list:
                                # logger.warning(f"clean a counter: {o} {_s}")
                                obj_sta = (o, _s)
                                break
                    else:
                        obj_sta = (o, s)

                    # assert obj_sta != None, (occupy_object_status_list, o, o_class_str)
                o_class_str = type(obj_sta[0]).__name__
                if len(self.world.get_objects_at(obj_sta[0].location, Plate)) > 0 and o_class_str in [
                    "Lettuce",
                    "Bread",
                ]:
                    obj_sta = (obj_sta[0], "in_plate")
                self.prev_task = ("clean_a_counter", center, o_class_str, (obj_sta[0], obj_sta[1]))
                self.text_agent.assigned_pickup_target = obj_sta[0]
                logger.error(self.text_agent.assigned_pickup_target)

                o_class_str_lower = o_class_str.lower()
                clean_a_counter_subtasks = [
                    f"pickup_{o_class_str_lower}_{obj_sta[1]}" if obj_sta[1] != "" else f"pickup_{o_class_str_lower}",
                ]
                if o_class_str not in ["Plate"]:
                    clean_a_counter_subtasks.append("drop_food")
                if self.agent.holding is not None:
                    clean_a_counter_subtasks.insert(0, "put_onto_edge_counter" if center else "put_onto_counter")
                if len(self.world.get_objects_at(obj_sta[0].location, Plate)) > 0:
                    clean_a_counter_subtasks.append("put_onto_edge_counter" if center else "put_onto_counter")

                clean_a_counter_subtasks = {(o_class_str, obj_sta[1]): [clean_a_counter_subtasks]}
                assert self._check_process(clean_a_counter_subtasks)
                self._clean_a_counter_forward_index = self._processes_transform(clean_a_counter_subtasks)
                logger.debug(f"clean a counter forward index:\n {pretty_repr(self._clean_a_counter_forward_index)}")
            else:
                self.prev_task = None
                self._clean_a_counter_forward_index = {}

        valid_actions = self.text_agent.get_valid_actions()
        if self.prev_task is not None:
            obj_sta = (self.prev_task[2], self.prev_task[3][1])
            while current_subtask is None:
                n_try += 1
                next_subtask_cands = self._clean_a_counter_forward_index[obj_sta][tuple(self.prev_subtasks)]
                if next_subtask_cands is True:
                    current_subtask = True
                    break
                else:
                    for n_t in next_subtask_cands:
                        next_subtask = n_t[0]
                        next_subtask_cond = n_t[1] is None or n_t[1](*n_t[2])
                        if next_subtask in valid_actions and next_subtask_cond:
                            current_subtask = next_subtask
                            break
                if current_subtask is None:
                    if len(self.prev_subtasks) > 0:
                        trace_back_subtask = self.prev_subtasks.pop()
                        logger.trace(f"trace_back {trace_back_subtask}, traj {self.prev_subtasks}")
                    else:
                        break
                logger.trace(f"n_try {n_try}, current_subtask {current_subtask}")
                if n_try >= self.max_n_try:
                    logger.warning(f"try more than {self.max_n_try} times")
                    break
        if current_subtask is None:
            logger.warning(f"Cannot clean a{' center ' if center else ' '}counter!")
            logger.warning(occupy_object_status_list)
            logger.warning(occupy_counter_list)
            end = True
            status = (
                f"Failed: no{' center ' if center else ' '}counter is occupied, you should continue to fulfill orders"
            )
        elif current_subtask is True:
            end = True
            status = "Succeeded"
        else:
            end = False
            status = current_subtask

        if end:
            self.prev_task = None
            self.prev_subtasks = []
        else:
            self.prev_subtasks.append(current_subtask)
        return (end, status)
