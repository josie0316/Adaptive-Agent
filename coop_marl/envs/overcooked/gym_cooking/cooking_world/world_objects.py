from typing import List

from gym_cooking.cooking_world.abstract_classes import *
from gym_cooking.cooking_world.constants import *


# Static Object
class Floor(StaticObject):
    def __init__(self, location):
        super().__init__(location, True)

    def accepts(self, dynamic_objects) -> bool:
        return False

    def file_name(self) -> str:
        return "floor"


class Counter(StaticObject):
    def __init__(self, location, is_center: bool = False):
        super().__init__(location, False)
        self.is_center = is_center

    def accepts(self, dynamic_objects) -> bool:
        return True

    def file_name(self) -> str:
        return "counter"


class DeliverSquare(StaticObject):
    def __init__(self, location):
        super().__init__(location, False)

    def filter_obj(self, objects: List[DynamicObject], obj_type):
        filtered_objects = [obj for obj in objects if isinstance(obj, obj_type)]
        if len(filtered_objects) > 1:
            # raise Exception(f"Too many {obj_type} in one place!")
            return filtered_objects[0]
        elif len(filtered_objects) == 1:
            return filtered_objects[0]
        else:
            return None

    def check_accept(self, objects: List[DynamicObject]):
        # order = [Container, Food]
        # res = [False, False]
        # print(objects)
        # print(objects[0].content)
        accept = False
        # for i, obj_type in enumerate(order):
        #     obj = self.filter_obj(objects, obj_type)
        #     if obj:
        #         res[i] = True
        # accept = all(res)
        # print(res, accept)

        # is a plate and it does contains things
        if isinstance(objects[0], Container) and len(objects[0].content) > 0:
            accept = True
        # print(accept)
        return accept

    def accepts(self, dynamic_objects) -> bool:
        accept = self.check_accept(dynamic_objects)
        return accept

    def file_name(self) -> str:
        return "delivery"


class Dustbin(StaticObject):
    def __init__(self, location):
        super().__init__(location, False)

    def accepts(self, dynamic_objects) -> bool:
        return False

    def file_name(self) -> str:
        return "Dustbin"


# class CenterCounter(Counter):
#     def __init__(self, location):
#         super().__init__(location)

#     def accepts(self, dynamic_objects) -> bool:
#         return True

#     def file_name(self) -> str:
#         return "CenterCounter"


# class EdgeCounter(Counter):
#     def __init__(self, location):
#         super().__init__(location)

#     def accepts(self, dynamic_objects) -> bool:
#         return True

#     def file_name(self) -> str:
#         return "EdgeCounter"


class CutBoard(StaticObject, ActionObject):
    def __init__(self, location):
        super().__init__(location, False)
        self.content = None

    def action(self, dynamic_objects: List, agent):
        if len(dynamic_objects) == 1:
            try:
                return dynamic_objects[0].chop(agent)
            except AttributeError:
                return False
        return False

    def accepts(self, dynamic_objects) -> bool:
        return len(dynamic_objects) == 1 and isinstance(dynamic_objects[0], ChopFood)

    def file_name(self) -> str:
        return "cutboard"


# ProgressingObject
class Blender(StaticObject, ProgressingObject):
    def __init__(self, location):
        super().__init__(location, False)
        self.content = None

    def progress(self, dynamic_objects):
        assert len(dynamic_objects) < 2, "Too many Dynamic Objects placed into the Blender"
        if not dynamic_objects:
            self.content = None
            return
        elif not self.content:
            self.content = dynamic_objects
        elif self.content:
            if self.content[0] == dynamic_objects[0]:
                self.content[0].blend()
            else:
                self.content = dynamic_objects

    # if accepts, mark the player name to the object
    def accepts(self, dynamic_objects) -> bool:
        return len(dynamic_objects) == 1 and isinstance(dynamic_objects[0], BlenderFood)

    def file_name(self) -> str:
        return "blender3"


class Pot(StaticObject, ProgressingObject):
    pass


class SoupPot(Pot):
    def __init__(self, location):
        super().__init__(location, False)
        self.content = None
        self.full = False  # to judge if the pot is full
        self.powered = False

    def progress(self, dynamic_objects):
        if not self.powered:
            return
        if not dynamic_objects:
            self.content = None
            return
        else:
            self.content.blend()

    def accepts(self, dynamic_objects) -> bool:
        if (
            len(dynamic_objects) == 1
            and isinstance(dynamic_objects[0], Food)
            and not self.powered
            and dynamic_objects[0].done()
        ):
            return True
        return False

    def file_name(self) -> str:
        return "souppot"


class Pan(Pot):
    def __init__(self, location):
        super().__init__(location, False)
        self.content = None
        self.full = False  # to judge if the pot is full
        self.powered = True

    def progress(self, dynamic_objects):
        if not dynamic_objects:
            self.content = None
            return
        else:
            self.content.blend()

    def accepts(self, dynamic_objects) -> bool:
        if len(dynamic_objects) == 1 and isinstance(dynamic_objects[0], Beef):
            return True
        return False

    def file_name(self) -> str:
        return "Pan"


class MixSoupPot(StaticObject, ProgressingObject):
    def __init__(self, location):
        super().__init__(location, False)
        self.content = None
        self.full = False  # to judge if the pot is full

    def progress(self, dynamic_objects):
        if not dynamic_objects:
            self.content = None
            return
        elif (not self.content) or len(self.content) < 3:
            self.content = dynamic_objects
        else:
            if self.content[0] == dynamic_objects[0]:
                for item in self.content:
                    item.blend()
            else:
                self.content = dynamic_objects

    def accepts(self, dynamic_objects) -> bool:
        if len(dynamic_objects) == 1 and isinstance(dynamic_objects[0], BlenderFood):
            if self.content:
                # return self.content[0] == dynamic_objects[0] and len(self.content) < 3
                if len(self.content) <= 3:
                    self.full = True
                return len(self.content) < 3
            else:
                self.full = False
                return True
        self.full = self.content is not None and len(self.content) == 3
        return False

    def file_name(self) -> str:
        return "souppot"


class FireExtinguisher(DynamicObject):
    def __init__(self, location):
        super().__init__(location)

    def file_name(self) -> str:
        return "fire_extinguisher"


class Fire(DynamicObject):
    def __init__(self, location):
        super().__init__(location)
        self.put_num = 0
        self.max_put_num = 5

    def putoff(self):
        if self.put_num != self.max_put_num:
            self.put_num += 1

    def file_name(self) -> str:
        return "fire"


class OnionStation(Station):
    def __init__(self, location):
        super().__init__(location, Onion)

    def file_name(self) -> str:
        return "FreshOnion"


class TomatoStation(Station):
    def __init__(self, location):
        super().__init__(location, Tomato)

    def file_name(self) -> str:
        return "FreshTomato"


class LettuceStation(Station):
    def __init__(self, location):
        super().__init__(location, Lettuce)

    def file_name(self) -> str:
        return "LettuceStation"


class CarrotStation(Station):
    def __init__(self, location):
        super().__init__(location, Carrot)

    def file_name(self) -> str:
        return "FreshCarrot"


class PlateStation(Station):
    def __init__(self, location):
        super().__init__(location, Plate)

    def file_name(self) -> str:
        return "PlateStation"


# Dynamic Object
class Plate(Container):
    def __init__(self, location):
        super().__init__(location)

    def add_content(self, content):
        if not isinstance(content, Food):
            raise TypeError(f"Only Food can be added to a plate! Tried to add {content.name()}")
        if not content.done() and not content.overcooked():
            raise Exception(f"Can't add food in unprepared state.")
        self.content.append(content)

    def file_name(self) -> str:
        return "Plate"


class Onion(ChopFood):
    # Dynamic Object

    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.chop_state == ChopFoodStates.CHOPPED:
            return True
        else:
            return False

    def mix(self, food: Food):
        if isinstance(food, Lettuce):
            new_obj = LettuceOnion(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, Tomato):
            return OnionTomato(self.location)
        elif isinstance(food, LettuceTomato):
            return LettuceOnionTomato(self.location)

    def file_name(self) -> str:
        if self.done():
            return "ChoppedOnion"
        else:
            return "FreshOnion"


class Tomato(ChopFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.chop_state == ChopFoodStates.CHOPPED:
            return True
        else:
            return False

    def mix(self, food: Food):
        if isinstance(food, Lettuce):
            return LettuceTomato(self.location)
        elif isinstance(food, Onion):
            return OnionTomato(self.location)
        elif isinstance(food, LettuceOnion):
            return LettuceOnionTomato(self.location)

    def file_name(self) -> str:
        if self.done():
            return "ChoppedTomato"
        else:
            return "FreshTomato"


class Lettuce(ChopFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.chop_state == ChopFoodStates.CHOPPED:
            return True
        else:
            return False

    def fresh(self):
        return not self.done()

    def mix(self, food: Food):
        if isinstance(food, Tomato):
            return LettuceTomato(self.location)
        elif isinstance(food, Onion):
            return LettuceOnion(self.location)
        elif isinstance(food, OnionTomato):
            return LettuceOnionTomato(self.location)
        elif isinstance(food, Beef):
            new_obj = BeefLettuce(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, BeefBurger):
            new_obj = BeefLettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, Bread):
            new_obj = LettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj

    def file_name(self) -> str:
        if self.done():
            return "ChoppedLettuce"
        else:
            return "FreshLettuce"


class Carrot(ChopFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.chop_state == ChopFoodStates.CHOPPED:
            return True
        else:
            return False

    def file_name(self) -> str:
        if self.done():
            return "ChoppedCarrot"
        else:
            return "FreshCarrot"


class LettuceOnion(BlenderFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.blend_state == BlenderFoodStates.MASHED:
            return True
        else:
            return False

    def overcooked(self):
        if self.blend_state == BlenderFoodStates.OVERCOOKED:
            return True
        else:
            return False

    def mix(self, food: Food):
        if isinstance(food, Tomato):
            return LettuceOnionTomato(self.location)

    def file_name(self) -> str:
        if self.overcooked():
            return "Overcooked_ChoppedLettuce-ChoppedOnion"
        elif self.done():
            return "ChoppedLettuce-ChoppedOnion_Soup"
        return "ChoppedLettuce-ChoppedOnion"


class LettuceTomato(BlenderFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.blend_state == BlenderFoodStates.MASHED:
            return True
        else:
            return False

    def overcooked(self):
        if self.blend_state == BlenderFoodStates.OVERCOOKED:
            return True
        else:
            return False

    def mix(self, food: Food):
        if isinstance(food, Onion):
            return LettuceOnionTomato(self.location)

    def file_name(self) -> str:
        if self.overcooked():
            return "Overcooked_ChoppedLettuce-ChoppedTomato"
        elif self.done():
            return "ChoppedLettuce-ChoppedTomato_Soup"
        return "ChoppedLettuce-ChoppedTomato"


class OnionTomato(BlenderFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.blend_state == BlenderFoodStates.MASHED:
            return True
        else:
            return False

    def overcooked(self):
        if self.blend_state == BlenderFoodStates.OVERCOOKED:
            return True
        else:
            return False

    def mix(self, food: Food):
        if isinstance(food, Lettuce):
            return LettuceOnionTomato(self.location)

    def file_name(self) -> str:
        if self.overcooked():
            return "Overcooked_ChoppedOnion-ChoppedTomato"
        elif self.done():
            return "ChoppedOnion-ChoppedTomato_Soup"
        return "ChoppedOnion-ChoppedTomato"


class LettuceOnionTomato(BlenderFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.blend_state == BlenderFoodStates.MASHED:
            return True
        else:
            return False

    def overcooked(self):
        if self.blend_state == BlenderFoodStates.OVERCOOKED:
            return True
        else:
            return False

    def file_name(self) -> str:
        if self.overcooked():
            return "Overcooked_ChoppedLettuce-ChoppedOnion-ChoppedTomato"
        elif self.done():
            return "ChoppedLettuce-ChoppedOnion-ChoppedTomato_Soup"
        return "ChoppedLettuce-ChoppedOnion-ChoppedTomato"


class Beef(BlenderFood):
    def __init__(self, location):
        super().__init__(location)

    def done(self):
        if self.blend_state == BlenderFoodStates.MASHED:
            return True
        else:
            return False

    def overcooked(self):
        if self.blend_state == BlenderFoodStates.OVERCOOKED:
            return True
        else:
            return False

    def in_progress(self):
        if self.blend_state == BlenderFoodStates.IN_PROGRESS:
            return True
        else:
            return False

    def fresh(self):
        return not (self.done() or self.overcooked())

    def mix(self, food: Food):
        if isinstance(food, Lettuce):
            new_obj = BeefLettuce(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, LettuceBurger):
            new_obj = BeefLettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, Bread):
            new_obj = BeefBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj

    def file_name(self) -> str:
        if self.overcooked():
            return "OvercookedBeef"
        elif self.done():
            return "FriedBeef"
        return "Beef"


class BeefStation(Station):
    def __init__(self, location):
        super().__init__(location, Beef)

    def file_name(self) -> str:
        return "BeefStation"


class Bread(DynamicObject, Food):
    def __init__(self, location):
        super().__init__(location)

    # def fresh(self):
    #     return False

    def done(self):
        return True

    def mix(self, food: Food):
        if isinstance(food, Lettuce):
            new_obj = LettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, Beef):
            new_obj = BeefBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj
        elif isinstance(food, BeefLettuce):
            new_obj = BeefLettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj

    def file_name(self) -> str:
        return "Bread"


class BreadStation(Station):
    def __init__(self, location):
        super().__init__(location, Bread)

    def file_name(self) -> str:
        return "BreadStation"


class BeefBurger(DynamicObject, Food):
    def __init__(self, location):
        super().__init__(location)
        self.content = ["FriedBeef", "Bread"]

    def mix(self, food: Food):
        if isinstance(food, Lettuce):
            new_obj = BeefLettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj

    def done(self):
        return True

    def file_name(self) -> str:
        return "BeefBurger"


class BeefLettuce(DynamicObject, Food):
    def __init__(self, location):
        super().__init__(location)
        self.content = ["FriedBeef", "ChoppedLettuce"]

    def mix(self, food: Food):
        if isinstance(food, Bread):
            new_obj = BeefLettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj

    def done(self):
        return True

    def file_name(self) -> str:
        return "BeefLettuce"


class LettuceBurger(DynamicObject, Food):
    def __init__(self, location):
        super().__init__(location)
        self.content = ["ChoppedLettuce", "Bread"]

    def mix(self, food: Food):
        if isinstance(food, Beef):
            new_obj = BeefLettuceBurger(self.location)
            new_obj.agents = self.agents + food.agents
            return new_obj

    def done(self):
        return True

    def file_name(self) -> str:
        return "LettuceBurger"


class BeefLettuceBurger(DynamicObject, Food):
    def __init__(self, location):
        super().__init__(location)
        self.content = ["FriedBeef", "ChoppedLettuce", "Bread"]

    def done(self):
        return True

    def file_name(self) -> str:
        return "BeefLettuceBurger"


class Agent(Object):
    def __init__(self, location, color, name, id):
        super().__init__(location, False, False)
        self.holding = None
        self.color = color
        self.name = name
        self.orientation = 1
        self.event_list = []
        self.current_event = None
        self.id = id
        # self.next_position = location

    def grab(self, obj: DynamicObject):
        self.holding = obj
        obj.move_to(self.location)

    def put_down(self, location):
        self.holding.move_to(location)
        self.holding = None

    def move_to(self, new_location):
        self.location = new_location
        if self.holding:
            self.holding.move_to(new_location)

    def change_orientation(self, new_orientation):
        assert 0 < new_orientation < 5
        self.orientation = new_orientation

    def file_name(self) -> str:
        pass


CapToText = {
    "Plate": "plate",
    "Lettuce": "lettuce",
    "Beef": "beef",
    "Bread": "bread",
    "BeefLettuce": "beeflettuce",
    "LettuceBurger": "lettuceburger",
    "BeefBurger": "beefburger",
    "BeefLettuceBurger": "beeflettuceburger",
    "Fire": "fire",
    "FireExtinguisher": "fireextinguisher",
    "CutBoard": "cutboard",
    "Pan": "pan",
    "Counter": "counter",
    "Dustbin": "dustbin",
    # "CenterCounter": "centercounter",
    # "EdgeCounter": "edgecounter",
}

TextToCap = {
    "plate": "Plate",
    "lettuce": "Lettuce",
    "beef": "Beef",
    "bread": "Bread",
    "beeflettuce": "BeefLettuce",
    "lettuceburger": "LettuceBurger",
    "beefburger": "BeefBurger",
    "beeflettuceburger": "BeefLettuceBurger",
    "fire": "Fire",
    "fireextinguisher": "FireExtinguisher",
    "cutboard": "CutBoard",
    "pan": "Pan",
    "counter": "Counter",
    "dustbin": "Dustbin",
    # "centercounter": "CenterCounter",
    # "edgecounter": "EdgeCounter",
}

StringToClass = {
    "Floor": Floor,
    "Counter": Counter,
    "CutBoard": CutBoard,
    "DeliverSquare": DeliverSquare,
    "Tomato": Tomato,
    "Lettuce": Lettuce,
    "FreshLettuce": Lettuce,
    "ChoppedLettuce": Lettuce,
    "Onion": Onion,
    "Plate": Plate,
    "Agent": Agent,
    "Blender": Blender,
    "Carrot": Carrot,
    "OnionStation": OnionStation,
    "TomatoStation": TomatoStation,
    "LettuceStation": LettuceStation,
    "CarrotStation": CarrotStation,
    "PlateStation": PlateStation,
    "SoupPot": SoupPot,
    "Pan": Pan,
    "Dustbin": Dustbin,
    "LettuceOnion": LettuceOnion,
    "LettuceTomato": LettuceTomato,
    "OnionTomato": OnionTomato,
    "LettuceOnionTomato": LettuceOnionTomato,
    "FireExtinguisher": FireExtinguisher,
    "Fire": Fire,
    "Beef": Beef,
    "OvercookedBeef": Beef,
    "FriedBeef": Beef,
    "Bread": Bread,
    "BeefBurger": BeefBurger,
    "BeefLettuce": BeefLettuce,
    "LettuceBurger": LettuceBurger,
    "BeefLettuceBurger": BeefLettuceBurger,
    "BeefStation": BeefStation,
    "BreadStation": BreadStation,
    # "CenterCounter": CenterCounter,
    # "EdgeCounter": EdgeCounter,
}

ClassToString = {
    Floor: "Floor",
    Counter: "Counter",
    CutBoard: "CutBoard",
    DeliverSquare: "DeliverSquare",
    Tomato: "Tomato",
    Lettuce: "Lettuce",
    Onion: "Onion",
    Plate: "Plate",
    Agent: "Agent",
    Blender: "Blender",
    Carrot: "Carrot",
    OnionStation: "OnionStation",
    TomatoStation: "TomatoStation",
    LettuceStation: "LettuceStation",
    CarrotStation: "CarrotStation",
    PlateStation: "PlateStation",
    SoupPot: "SoupPot",
    Pan: "Pan",
    Dustbin: "Dustbin",
    LettuceOnion: "LettuceOnion",
    LettuceTomato: "LettuceTomato",
    OnionTomato: "OnionTomato",
    LettuceOnionTomato: "LettuceOnionTomato",
    FireExtinguisher: "FireExtinguisher",
    Fire: "Fire",
    Beef: "Beef",
    Bread: "Bread",
    BeefBurger: "BeefBurger",
    BeefLettuce: "BeefLettuce",
    LettuceBurger: "LettuceBurger",
    BeefLettuceBurger: "BeefLettuceBurger",
    BeefStation: "BeefStation",
    BreadStation: "BreadStation",
    # CenterCounter: "CenterCounter",
    # EdgeCounter: "EdgeCounter",
}

STATIC_CLASSES = [
    Floor,
    Counter,
    CutBoard,
    DeliverSquare,
    Blender,
    OnionStation,
    TomatoStation,
    LettuceStation,
    CarrotStation,
    SoupPot,
    Pan,
    Dustbin,
    PlateStation,
    BeefStation,
    BreadStation,
    # CenterCounter,
    # EdgeCounter,
]
GAME_CLASSES = [
    Floor,
    Counter,
    CutBoard,
    DeliverSquare,
    Tomato,
    Lettuce,
    Onion,
    Plate,
    Agent,
    Blender,
    Carrot,
    OnionStation,
    TomatoStation,
    LettuceStation,
    CarrotStation,
    SoupPot,
    Pan,
    Dustbin,
    LettuceOnion,
    LettuceTomato,
    OnionTomato,
    LettuceOnionTomato,
    FireExtinguisher,
    Fire,
    Beef,
    Bread,
    BeefBurger,
    BeefLettuce,
    LettuceBurger,
    BeefLettuceBurger,
    PlateStation,
    BeefStation,
    BreadStation,
    # CenterCounter,
    # EdgeCounter,
]
GAME_CLASSES_STATE_LENGTH = [
    (Floor, 1),
    (Counter, 1),
    (CutBoard, 1),
    (DeliverSquare, 1),
    (Tomato, 2),
    (Lettuce, 2),
    (Onion, 3),
    (Plate, 1),
    (Agent, 5),
    (Blender, 1),
    (Carrot, 3),
    (OnionStation, 1),
    (TomatoStation, 1),
    (LettuceStation, 1),
    (CarrotStation, 1),
    (SoupPot, 1),
    (Pan, 1),
    (Dustbin, 1),
    (LettuceOnion, 2),
    (LettuceTomato, 2),
    (OnionTomato, 2),
    (LettuceOnionTomato, 2),
    (FireExtinguisher, 1),
    (Fire, 1),
    (Beef, 2),
    (Bread, 1),
    (BeefBurger, 2),
    (BeefLettuce, 2),
    (LettuceBurger, 2),
    (BeefLettuceBurger, 2),
    (PlateStation, 1),
    (BeefStation, 1),
    (BreadStation, 1),
    # (CenterCounter, 1),
    # (EdgeCounter, 1),
]
GAME_CLASSES_HOLDABLE_IDX = {
    cls: i
    for i, cls in enumerate(
        [
            "Tomato",
            "Lettuce",
            "Onion",
            "Plate",
            "Carrot",
            "LettuceOnion",
            "LettuceTomato",
            "OnionTomato",
            "LettuceOnionTomato",
            "Beef",
            "Bread",
            "BeefBurger",
            "BeefLettuce",
            "LettuceBurger",
            "BeefLettuceBurger",
        ]
    )
}
FOOD_CLASSES = [
    "Tomato",
    "Lettuce",
    "Onion",
    "Carrot",
    "LettuceOnion",
    "LettuceTomato",
    "OnionTomato",
    "LettuceOnionTomato",
    "Beef",
    "Bread",
    "BeefBurger",
    "BeefLettuce",
    "LettuceBurger",
    "BeefLettuceBurger",
]
FOOD_CLASSES_IDX = {cls: i for i, cls in enumerate(FOOD_CLASSES)}
OBJ_IDX = {ClassToString[cls]: i for i, cls in enumerate(GAME_CLASSES[1:])}
OBJ2LABEL = {
    Floor: " ",
    Counter: "-",
    CutBoard: "/",
    DeliverSquare: "*",
    Plate: "p",
    Blender: "E",
    OnionStation: "O",
    TomatoStation: "T",
    LettuceStation: "L",
    CarrotStation: "C",
    PlateStation: "P",
    SoupPot: "S",
    Pan: "N",
    Dustbin: "D",
    FireExtinguisher: "F",
    Fire: "f",
    Bread: "r",
    BeefBurger: "h",
    BeefLettuce: "i",
    LettuceBurger: "j",
    BeefLettuceBurger: "k",
    BeefStation: "B",
    BreadStation: "R",
}

CHOPFOOD2LABEL = {
    Tomato: {False: "t", True: "!"},
    Lettuce: {False: "l", True: "@"},
    Onion: {False: "o", True: "#"},
    Carrot: {False: "c", True: "$"},
}

BLENDERFOOD2LABEL = {
    LettuceOnion: {False: "a", True: "A", "overcooked": "^"},
    LettuceTomato: {False: "d", True: "=", "overcooked": "&"},
    OnionTomato: {False: "e", True: "E", "overcooked": "("},
    LettuceOnionTomato: {False: "g", True: "G", "overcooked": ")"},
    Beef: {False: "b", True: "%", "overcooked": "|"},
}

ACTION2LABEL = {1: chr(8592), 2: chr(8594), 3: chr(8595), 4: chr(8593)}
