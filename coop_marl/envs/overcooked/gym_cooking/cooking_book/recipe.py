import numpy as np
from gym_cooking.cooking_world.cooking_world import CookingWorld
from gym_cooking.cooking_world.world_objects import *


class NodeTypes(Enum):
    CHECKPOINT = "Checkpoint"
    ACTION = "Action"


class RecipeNode:
    def __init__(
        self,
        root_type,
        id_num,
        name,
        parent=None,
        conditions=None,
        contains=None,
        node_type=NodeTypes.CHECKPOINT,
        contains_num=1,
        refactor=1,
    ):
        self.parent = parent
        self.achieved = False
        self.achieved_num = 0
        self.id_num = id_num
        self.root_type = root_type
        self.conditions = conditions or []
        self.contains = contains or []
        self.world_objects = []
        self.name = name
        self.node_type = node_type
        self.contains_num = contains_num
        self.refactor = refactor
        self.players = []

    def is_leaf(self):
        return not bool(self.contains)


class Recipe:
    def __init__(
        self, root_node: RecipeNode, name=None, filename=None, remain_time=0, score_factor=1.0, foodname: str = ""
    ):
        self.root_node = root_node
        self.node_list = [root_node] + self.expand_child_nodes(root_node)
        self.name = name
        self.complete_num = 0
        self.filename = filename
        self.max_remain_time = remain_time
        self.remain_time = remain_time
        self.score_factor = score_factor
        self.foodname = foodname

    def file_name(self):
        return self.filename

    def refactor(self, num_goals):
        refactors = np.zeros(num_goals, dtype=np.int32)
        for node in self.node_list:
            # goals[node.id_num] = int(not node.achieved)
            refactors[node.id_num] = int(node.refactor)
        return refactors

    def goals_completed(self, num_goals):
        goals = np.zeros(num_goals, dtype=np.int32)
        for node in self.node_list:
            # goals[node.id_num] = int(not node.achieved)
            goals[node.id_num] = int(node.achieved_num)
        return goals

    def completed(self):
        return self.root_node.achieved

    def reset_state(self):
        self.complete_num = 0
        for node in self.node_list:
            node.achieved = False
            node.achieved_num = 0
            node.world_objects = []

    def update_recipe_state(self, world: CookingWorld):
        # check which node is achieved
        # reason for reversed: each time, check the condition of its child to build a tree
        for node in reversed(self.node_list):
            node.achieved = False
            node.achieved_num = 0
            node.world_objects = []
            node.players = []

            # no chance to achieve
            if not all(contains.achieved_num > 0 for contains in node.contains):
                continue

            # may achieve
            for obj in world.world_objects[node.name]:
                # check for all conditions and finish players
                conditions, players = self.check_conditions(node, obj)
                if conditions:
                    node.world_objects.append(obj)
                    node.achieved = True
                    node.achieved_num += 1
                    # print("achieve")
            # if self.complete_num > 0:
            #     print("complete")
            node.achieved_num += self.complete_num * node.contains_num
        if self.root_node.achieved:
            # print("complete")
            self.complete_num += 1

            location = [obj.location for obj in self.root_node.world_objects]
            players, final_players, _ = world.clear_deliver(location)

            # world_objects = self.node_list[1].world_objects

            # for obj in world_objects:
            #     if obj.location == self.root_node.world_objects[0].location:
            #         obj.move_to((obj.location[0]+1, obj.location[1]))
            return len(self.root_node.world_objects), players, final_players
        return 0, [], []

    def expand_child_nodes(self, node: RecipeNode):
        child_nodes = []
        for child in node.contains:
            child_nodes.extend(self.expand_child_nodes(child))
        return node.contains + child_nodes

    @staticmethod
    def check_conditions(node: RecipeNode, world_object):
        for condition in node.conditions:
            if getattr(world_object, condition[0]) != condition[1]:
                return False, []
        else:
            all_contained = []
            all_players = []
            # check if the containers contains all the needed objects
            for contains in node.contains:
                # all_contained.append(any([obj.location == world_object.location for obj in contains.world_objects]))
                contained = []
                for obj in contains.world_objects:
                    if obj.location == world_object.location:
                        contained.append(True)
                        # all_players.append(obj.player)
                all_contained.append(any(contained))
            return all(all_contained), all_players

    def remove_object(self, world: CookingWorld):
        world_objects = self.node_list[1].world_objects
        for obj in world_objects:
            if obj.location == self.root_node.world_objects[0].location:
                obj.remove(world)
                world.delete_object(obj)


class Order:
    def __init__(self, name, time=40):
        self.name = name
        self.time = time
        self.late = False

    def progress_time(self):
        time = max(0, time - 1)
        if time == 0:
            self.late = True
            return True
        return False
