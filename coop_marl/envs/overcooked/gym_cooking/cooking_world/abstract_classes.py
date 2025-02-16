from abc import ABC, abstractmethod

from gym_cooking.cooking_world.constants import *


class Object(ABC):
    def __init__(self, location, movable, walkable):
        self.location = location
        self.movable = movable  # you can pick this one up
        self.walkable = walkable  # you can walk on it
        self.agents = []

    def name(self) -> str:
        return type(self).__name__

    def move_to(self, new_location):
        self.location = new_location

    @abstractmethod
    def file_name(self) -> str:
        pass


class ActionObject(ABC):
    @abstractmethod
    def action(self, objects, agent):
        pass


class ProgressingObject(ABC):
    @abstractmethod
    def progress(self, dynamic_objects):
        pass


class StaticObject(Object):
    def __init__(self, location, walkable):
        super().__init__(location, False, walkable)

    def move_to(self, new_location):
        raise Exception(f"Can't move static object {self.name()}")

    @abstractmethod
    def accepts(self, dynamic_objects) -> bool:
        pass


class DynamicObject(Object, ABC):
    def __init__(self, location):
        super().__init__(location, True, False)


class Station(StaticObject):
    def __init__(self, location, food=None):
        super().__init__(location, False)
        self.food = food

    def get_food(self):
        return self.food(self.location)

    def accepts(self, dynamic_objects) -> bool:
        return False


class Container(DynamicObject, ABC):
    def __init__(self, location, content=None):
        super().__init__(location)
        self.content = content or []

    def move_to(self, new_location):
        for content in self.content:
            content.move_to(new_location)
        self.location = new_location

    def add_content(self, content):
        self.content.append(content)


    def remove(self, world):
        for content in self.content:
            world.delete_object(content)
        self.content = []


class Food:
    @abstractmethod
    def done(self):
        pass


class ChopFood(DynamicObject, Food, ABC):
    def __init__(self, location):
        super().__init__(location)
        self.chop_state = ChopFoodStates.FRESH
        self.chop_num = 0
        self.max_chop_num = 8

    def chop(self, agent):
        if self.done():
            return False
        self.chop_num += 1
        if self.chop_num >= self.max_chop_num:
            self.chop_state = ChopFoodStates.CHOPPED

        return True


class BlenderFood(DynamicObject, Food, ABC):
    def __init__(self, location):
        super().__init__(location)
        self.current_progress = 30
        self.max_progress = 0
        self.min_progress = 30
        self.overcooked_progress = -40
        self.blend_state = BlenderFoodStates.FRESH

    def blend(self):
        # if self.done():
        #     return False
        if (
            self.blend_state == BlenderFoodStates.FRESH
            or self.blend_state == BlenderFoodStates.IN_PROGRESS
            or self.blend_state == BlenderFoodStates.MASHED
        ):
            self.current_progress -= 1
            self.current_progress = max(-40, self.current_progress)
            self.blend_state = (
                BlenderFoodStates.IN_PROGRESS if self.current_progress > self.max_progress else BlenderFoodStates.MASHED
            )
            if self.current_progress <= self.overcooked_progress:
                self.blend_state = BlenderFoodStates.OVERCOOKED
        return True


ABSTRACT_GAME_CLASSES = (
    ActionObject,
    ProgressingObject,
    Container,
    Food,
    ChopFood,
    DynamicObject,
    StaticObject,
    BlenderFood,
)

STATEFUL_GAME_CLASSES = (ChopFood, BlenderFood)
