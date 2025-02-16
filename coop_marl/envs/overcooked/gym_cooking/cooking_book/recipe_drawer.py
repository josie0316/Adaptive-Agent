from copy import deepcopy

from gym_cooking.cooking_book.recipe import Recipe, RecipeNode
from gym_cooking.cooking_world.world_objects import *


def id_num_generator():
    num = 0
    while True:
        yield num
        num += 1


id_generator = id_num_generator()

#  Basic food Items
# root_type, id_num, parent=None, conditions=None, contains=None
ChoppedLettuce = RecipeNode(
    root_type=Lettuce,
    id_num=next(id_generator),
    name="Lettuce",
    conditions=[("chop_state", ChopFoodStates.CHOPPED)],
)
ChoppedOnion = RecipeNode(
    root_type=Onion,
    id_num=next(id_generator),
    name="Onion",
    conditions=[("chop_state", ChopFoodStates.CHOPPED)],
)
ChoppedTomato = RecipeNode(
    root_type=Tomato,
    id_num=next(id_generator),
    name="Tomato",
    conditions=[("chop_state", ChopFoodStates.CHOPPED)],
)
ChoppedCarrot = RecipeNode(
    root_type=Carrot,
    id_num=next(id_generator),
    name="Carrot",
    conditions=[("chop_state", ChopFoodStates.CHOPPED)],
)
MashedCarrot = RecipeNode(
    root_type=Carrot,
    id_num=next(id_generator),
    name="Carrot",
    conditions=[("blend_state", BlenderFoodStates.MASHED)],
)

# LettuceTomato = RecipeNode(root_type=None, id_num=next(id_generator),
#                            contains=

# Salad Plates
LettuceSaladPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedLettuce],
)
TomatoSaladPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedTomato],
)
TomatoLettucePlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedTomato, ChoppedLettuce],
)
TomatoCarrotPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedTomato, ChoppedCarrot],
)
TomatoLettuceOnionPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedTomato, ChoppedLettuce, ChoppedOnion],
)
ChoppedOnionPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedOnion],
)
ChoppedCarrotPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[ChoppedCarrot],
)
MasedCarrotPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[MashedCarrot],
)

# Soup

# Delivered Salads
LettuceSalad = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[LettuceSaladPlate],
)
TomatoSalad = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[TomatoSaladPlate],
)
TomatoLettuceSalad = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[TomatoLettucePlate],
)
TomatoCarrotSalad = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[TomatoCarrotPlate],
)
ChoppedOnion = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[ChoppedOnionPlate],
)
ChoppedCarrot = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[ChoppedCarrotPlate],
)
MashedCarrot = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[MasedCarrotPlate],
)

LettuceTomatoSoup = RecipeNode(
    root_type=LettuceTomato,
    id_num=next(id_generator),
    name="LettuceTomato",
    conditions=[("blend_state", BlenderFoodStates.MASHED)],
)
LettuceOnionSoup = RecipeNode(
    root_type=LettuceOnion,
    id_num=next(id_generator),
    name="LettuceOnion",
    conditions=[("blend_state", BlenderFoodStates.MASHED)],
)
OnionTomatoSoup = RecipeNode(
    root_type=OnionTomato,
    id_num=next(id_generator),
    name="OnionTomato",
    conditions=[("blend_state", BlenderFoodStates.MASHED)],
)
LettuceOnionTomatoSoup = RecipeNode(
    root_type=LettuceOnionTomato,
    id_num=next(id_generator),
    name="LettuceOnionTomato",
    conditions=[("blend_state", BlenderFoodStates.MASHED)],
)
LettuceBurgerFood = RecipeNode(
    root_type=LettuceBurger,
    id_num=next(id_generator),
    name="LettuceBurger",
    conditions=None,
)
BeefBurgerFood = RecipeNode(root_type=BeefBurger, id_num=next(id_generator), name="BeefBurger", conditions=None)
BeefLettuceBurgerFood = RecipeNode(
    root_type=BeefLettuceBurger,
    id_num=next(id_generator),
    name="BeefLettuceBurger",
    conditions=None,
)

LettuceTomatoSoupPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[LettuceTomatoSoup],
)
LettuceOnionSoupPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[LettuceOnionSoup],
)
OnionTomatoSoupPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[OnionTomatoSoup],
)
LettuceOnionTomatoSoupPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[LettuceOnionTomatoSoup],
)
LettuceBurgerPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[LettuceBurgerFood],
)
BeefBurgerPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[BeefBurgerFood],
)
BeefLettuceBurgerPlate = RecipeNode(
    root_type=Plate,
    id_num=next(id_generator),
    name="Plate",
    conditions=None,
    contains=[BeefLettuceBurgerFood],
)


LettuceTomatoSoupDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[LettuceTomatoSoupPlate],
)
LettuceOnionSoupDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[LettuceOnionSoupPlate],
)
OnionTomatoSoupDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[OnionTomatoSoupPlate],
)
LettuceOnionTomatoSoupDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[LettuceOnionTomatoSoupPlate],
)
LettuceBurgerDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[LettuceBurgerPlate],
)
BeefBurgerDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[BeefBurgerPlate],
)
BeefLettuceBurgerDeliver = RecipeNode(
    root_type=DeliverSquare,
    id_num=next(id_generator),
    name="DeliverSquare",
    conditions=None,
    contains=[BeefLettuceBurgerPlate],
)

# this one increments one further and is thus the amount of ids we have given since
# we started counting at zero.
NUM_GOALS = next(id_generator)

RECIPES = {
    "LettuceSalad": lambda: deepcopy(Recipe(LettuceSalad, name="LettuceSalad")),
    "TomatoSalad": lambda: deepcopy(Recipe(TomatoSalad, name="TomatoSalad")),
    "TomatoLettuceSalad": lambda: deepcopy(Recipe(TomatoLettuceSalad, name="TomatoLettuceSalad")),
    "TomatoCarrotSalad": lambda: deepcopy(Recipe(TomatoCarrotSalad, name="TomatoCarrotSalad")),
    # "TomatoLettuceOnionSalad": lambda: deepcopy(Recipe(TomatoLettuceOnionSalad, name='TomatoLettuceOnionSalad')),
    "ChoppedCarrot": lambda: deepcopy(Recipe(ChoppedCarrot, name="ChoppedCarrot")),
    "ChoppedOnion": lambda: deepcopy(Recipe(ChoppedOnion, name="ChoppedOnion")),
    "MashedCarrot": lambda: deepcopy(Recipe(MashedCarrot, name="MashedCarrot")),
    "LettuceTomatoSoupDeliver": lambda: deepcopy(
        Recipe(
            LettuceTomatoSoupDeliver,
            name="LettuceTomatoSoupDeliver",
            filename="ChoppedLettuce-ChoppedTomato_Soup",
            remain_time=60 * 2.5,
        )
    ),
    "LettuceOnionSoupDeliver": lambda: deepcopy(
        Recipe(
            LettuceOnionSoupDeliver,
            name="LettuceOnionSoupDeliver",
            filename="ChoppedLettuce-ChoppedOnion_Soup",
            remain_time=60 * 2.5,
        )
    ),
    "OnionTomatoSoupDeliver": lambda: deepcopy(
        Recipe(
            OnionTomatoSoupDeliver,
            name="OnionTomatoSoupDeliver",
            filename="ChoppedOnion-ChoppedTomato_Soup",
            remain_time=60 * 2.5,
        )
    ),
    "LettuceOnionTomatoSoupDeliver": lambda: deepcopy(
        Recipe(
            LettuceOnionTomatoSoupDeliver,
            name="LettuceOnionTomatoSoupDeliver",
            filename="ChoppedLettuce-ChoppedOnion-ChoppedTomato_Soup",
            remain_time=70 * 2.5,
        )
    ),
    "LettuceBurgerDeliver": lambda: deepcopy(
        Recipe(
            LettuceBurgerDeliver,
            name="LettuceBurgerDeliver",
            filename="LettuceBurger",
            foodname="LettuceBurger",
            remain_time=40 * 5,
            score_factor=0.75,
        )
    ),
    "BeefBurgerDeliver": lambda: deepcopy(
        Recipe(
            BeefBurgerDeliver,
            name="BeefBurgerDeliver",
            filename="BeefBurger",
            foodname="BeefBurger",
            remain_time=50 * 5,
            score_factor=1,
        )
    ),
    "BeefLettuceBurgerDeliver": lambda: deepcopy(
        Recipe(
            BeefLettuceBurgerDeliver,
            name="BeefLettuceBurgerDeliver",
            filename="BeefLettuceBurger",
            foodname="BeefLettuceBurger",
            remain_time=60 * 5,
            score_factor=1.25,
        )
    ),
    "BeefBurger": lambda: deepcopy(
        Recipe(
            BeefBurgerDeliver,
            name="BeefBurgerDeliver",
            filename="BeefBurger",
            foodname="BeefBurger",
            remain_time=50 * 5,
            score_factor=1,
        )
    ),
    "BeefLettuceBurger": lambda: deepcopy(
        Recipe(
            BeefLettuceBurgerDeliver,
            name="BeefLettuceBurgerDeliver",
            filename="BeefLettuceBurger",
            foodname="BeefLettuceBurger",
            remain_time=60 * 5,
            score_factor=1.25,
        )
    ),
    "LettuceBurger": lambda: deepcopy(
        Recipe(
            LettuceBurgerDeliver,
            name="LettuceBurgerDeliver",
            filename="LettuceBurger",
            foodname="LettuceBurger",
            remain_time=40 * 5,
            score_factor=0.75,
        )
    ),
}
