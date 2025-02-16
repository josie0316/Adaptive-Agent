ACT_GOAL_PROMPT = """\
# Game Introduction

## Game Scene

The game environment is set in a kitchen, designed for a cooking challenge. The layout includes various stations and essential elements for gameplay. Here's a detailed breakdown of the scene:

- **Ingredient Stations**: Distribution stations for picking up `Lettuce`, `Beef` and `Bread`.
- **Cooking and Preparation Tools**:
  - **Pans**: for cooking `Beef`.
  - **Cutboards**: for preparing `Lettuce`.
- **Plate Station**: for picking up empty plates.
- **Fire Extinguisher**: for extinguishing fires and can be moved.
- **Serving Area**: for serving orders.

You are controlling a chef in the kitchen, and your goal is to fulfill customer orders efficiently and accurately by writing codes to improve your policies in the game.

## Game Mechanisms

### Game Objects

Each object is a represented as a tuple of `(object_name, object_status)`.
    - **Beef**: Includes `("Beef", "Fresh")`, `("Beef", "In-progress")`, `("Beef", "Well-cooked")`, `("Beef", "Overcooked")`. Note that `("Beef", "In-progress")` will become `("Beef", "Well-cooked")` after a certain time, and `("Beef", "Well-cooked")` will become `("Beef", "Overcooked")` if left on the pan for too long.
    - **Lettuce**: Includes `("Lettuce", "Unchopped")` and `("Lettuce", "Chopped")`.
    - **Bread**: Represented as `("Bread", "")`.
    - **BeefLettuce**: A mixture of ingredients, represented as `("BeefLettuce", "")`.
    - **Burgers**: Types include `("BeefBurger", "")`, `("LettuceBurger", "")`, and `("BeefLettuceBurger", "")`.
    - **Plate**: Represented as `("Plate", "")`.
    - **FireExtinguisher**: Represented as `("FireExtinguisher", "")`.
    - **Fire**: Indicates an active fire, represented as `("Fire", "")`.

### Counters

Especially, we count the status of the counters in the kitchen:
    - "Empty": No object on the counter.

### Valid Actions in Code

To play the game, you can use the following actions:

- **Prepare Actions**: Used to prepare individual ingredients. Each ingredient can be prepared with the option to either place it on a plate or not. Here are the valid prepare actions:
    - Preparing `("Beef", "Well-cooked")`: Get a `("Beef", "Fresh")` and cook it into a `("Beef", "In-progress")` and then a `("Beef", "Well-cooked")`. Pay attention to avoid overcooking it, which will result in a `("Beef", "Overcooked")` and a `("Fire", "")` in the pan.
      - `("prepare", {"food": "Beef", "plate": True})`
      - `("prepare", {"food": "Beef", "plate": False})`
    - Preparing `("Lettuce", "Chopped")`: Get a `("Lettuce", "Unchopped")` and chop it into a `("Lettuce", "Chopped")`.
        - `("prepare", {"food": "Lettuce", "plate": True})`
        - `("prepare", {"food": "Lettuce", "plate": False})`
    - Preparing `("Bread", "")`: Get a `("Bread", "")` and put it on the counter or in a plate.
      - `("prepare", {"food": "Bread", "plate": True})`
      - `("prepare", {"food": "Bread", "plate": False})`

    Note that when there is no `("Beef", "Fresh")`, `("Lettuce", "Unchopped")` or `("Bread", "")` in the kitchen, the prepare actions will automatically get the ingredients from the respective stations.

- **Assemble Actions**: Used to assemble burgers with the already prepared ingredients (`("Beef", "Well-cooked")`, `("Lettuce", "Chopped")` and `("Bread", "")`). These actions will only be performed if all required ingredients are ready. See the **Cookbook** section for the burger types and their ingredients.
  - `("assemble", {"food": "LettuceBurger"})`
  - `("assemble", {"food": "BeefBurger"})`
  - `("assemble", {"food": "BeefLettuceBurger"})`

- **Serve Actions**: Used to serve the assembled burgers to the customer.
  - `("serve", {"food": "BeefBurger"})`
  - `("serve", {"food": "LettuceBurger"})`
  - `("serve", {"food": "BeefLettuceBurger"})`

- **Put Out Fire Action**: Used to pick up the fire extinguisher and put out the fire on the pan when the `Beef` is overcooked and catches fire.
  - `("putout_fire", {})`

- **Clean A Counter Action**: Used to clean a counter by dropping all objects on it to the trash can.
  - `("clean_a_counter", {})`

### Cookbook

In this kitchen game, the goal is to prepare and serve burgers efficiently to earn points. The game features three types of burgers: `LettuceBurger`, `BeefBurger`, and `BeefLettuceBurger`. Here are the rules and how the actions fit into the gameplay:

- **LettuceBurger**:
  - **Ingredients**: `("Lettuce", "Chopped")`, `("Bread", "")`
  - **Preparation**:
    - Prepare `("Lettuce", "Chopped")` if not already prepared
    - Assemble the ingredients using the action: `("assemble", {"food": "LettuceBurger"})`
- **BeefBurger**:
  - **Ingredients**: `("Beef", "Well-cooked")`, `("Bread", "")`
  - **Preparation**:
    - Prepare `("Beef", "Well-cooked")`  if not already prepared
    - Assemble the ingredients using the action: `("assemble", {"food": "BeefBurger"})`
- **BeefLettuceBurger**:
  - **Ingredients**: `("Lettuce", "Chopped")`, `("Beef", "Well-cooked")`, `("Bread", "")`
  - **Preparation**:
    - Method One
        - Prepare `("Lettuce", "Chopped")` if not already prepared
        - Prepare `("Beef", "Well-cooked")` if not already prepared
        - Assemble the ingredients using the action: `("assemble", {"food": "BeefLettuceBurger"})`
    - Method Two
        - Prepare `("Lettuce", "Chopped")` if not already prepared
        - Assemble the ingredients using the action: `("assemble", {"food": "LettuceBurger"})`
        - Prepare `("Beef", "Well-cooked")` if not already prepared
        - Assemble the ingredients using the action: `("assemble", {"food": "BeefLettuceBurger"})`
    - Method Three
        - Prepare `("Beef", "Well-cooked")` if not already prepared
        - Assemble the ingredients using the action: `("assemble", {"food": "BeefBurger"})`
        - Prepare `("Lettuce", "Chopped")` if not already prepared
        - Assemble the ingredients using the action: `("assemble", {"food": "BeefLettuceBurger"})`
    - Method Four
        - If there is a prepared `("BeefLettuce", "")`, you can directly assemble the `BeefLettuceBurger` using the action: `("assemble", {"food": "BeefLettuceBurger"})`
Note:
- The `Bread` will be automatically used, from prepared `Bread` or the Bread Station, when the `assemble` action is performed. You can also prepare `Bread` in advance.
- **Preparation Flexibility**: You can complete a burger in a flexible order. For example, when making a `BeefLettuceBurger', you can prepare the `Lettuce` before the `Beef`, or vice versa.


### Scoring System

- **Points Earned**:
  There are orders from customers that need to be fulfilled. Each order has a specific point value:
  - `LettuceBurger`: 15 points
  - `BeefBurger`: 20 points
  - `BeefLettuceBurger`: 25 points
- **Points Lost**:
  - Missing an order results in losing 10 points. Ensure that each order is completed within the given time.
  - Serving an item that is not in the order lists also results in losing 10 points. Make sure only demanded burgers are served to customers.


### Important Tips
- **Unreachable Orders**: If the remaining time for an order is less than the time required to prepare the ingredients, it is better to skip that order and focus on the next one.


# Instructions

## Goal

Based on these settings, you need to consider how to play the game to achieve a higher score. Your decision-making process should consist of interleaving Observation, Thought and Action steps. Thought can reason about the current situation. Observation consists of the following information.

## Input Information

**Game History**:
    - A sequence of game scenes that have occurred in the past. Each game scene is consisted of:
        - Remained Timestep: The remained timestep of the game.
        - Score: The current score of the game.
        - Game State: The occurrences of objects, orders.
        - Action: Actions taken by your agent.
        - Delivery: The food that have been delivered and the corresponding obtained score.
        - Missed Orders: The orders that have not been completed in time and the obtained punished score.

### Game State

The current state of the game includes various details. Here's a detailed description based on the provided structure:

1. **Objects**:
    - The `objects` dictionary records the number of objects with different statuses. Each entry is a tuple of `(object_name, object_status)` mapped to `object_number`.
    - For example:
        - `("LettuceBurger", "") : 1` indicates that there is 1 `LettuceBurger`.

2. **Orders**:
    - The `orders` list contains the current orders that need to be completed. Each order is a dictionary with:
        - `name`: The name of the order, which can be `BeefBurger`, `LettuceBurger`, or `BeefLettuceBurger`.
        - `remain_time`: The remaining time to complete the order, with smaller remaining time indicating higher urgency.

#### Example Game State

Now I will show you a game state example. In this example, there are
- 1 fresh beef, 1 in-progress beef, and 1 overcooked beef. No well-cooked beef.
- 3 unchopped lettuce and 1 chopped lettuce.
- 4 bread prepared in advance.
- No assembled BeefLettuce, BeefBurgers, or BeefLettuceBurgers, but there is 1 LettuceBurger ready.
- 2 empty plates on counters.
- 18 empty counters.
- 1 fire extinguisher and no active fire.
- 2 orders pending: a BeefBurger with 30 seconds remaining and a LettuceBurger with 45 seconds remaining.

Note that you will only receive the json below:

```json
{
    "objects": {
        ("Beef", "Fresh"): 1,
        ("Beef", "In-progress"): 1,
        ("Beef", "Well-cooked"): 0,
        ("Beef", "Overcooked"): 1,
        ("Lettuce", "Unchopped"): 3,
        ("Lettuce", "Chopped"): 1,
        ("Bread", ""): 4,
        ("BeefLettuce", ""): 0,
        ("BeefBurger", ""): 0,
        ("LettuceBurger", ""): 1,
        ("BeefLettuceBurger", ""): 0,
        ("Plate", "Empty"): 2,
        ("FireExtinguisher", ""): 1,
        ("Fire", ""): 0
    },
    "counters": {
        "Empty": 18,
    },
    "orders": [
        {
            "name": "BeefBurger",
            "remain_time": 30
        },
        {
            "name": "LettuceBurger",
            "remain_time": 45
        }
    ]
}
```

# Examples

[Example Begin]

Observation 1:     Remained Timestep: 353,
    Score: 230.0,
    State: {'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 0,
                        ('Beef', 'Overcooked'): 3,
                        ('Beef', 'Well-cooked'): 0,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 1,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 0,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'LettuceBurger', 'remain_time': 85},
                       {'name': 'LettuceBurger', 'remain_time': 138},
                       {'name': 'LettuceBurger', 'remain_time': 170},
                       {'name': 'LettuceBurger', 'remain_time': 200}]},
            "counters": {
                "Empty": 18,
            },
    Delivery: {'LettuceBurger': 15.0},
    Missed Orders: {},
    Message: {},

Output Action: `("putout_fire", {})`

[Example End]


[Example Begin]

Observation 1:     Remained Timestep: 319,
    Score: 250.0,
    State: {'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 1,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 1,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 2,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 1,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 1},
            'orders': [{'name': 'BeefBurger', 'remain_time': 32},
                       {'name': 'BeefBurger', 'remain_time': 81},
                       {'name': 'BeefLettuceBurger', 'remain_time': 182},
                       {'name': 'BeefLettuceBurger', 'remain_time': 251}]},
    Delivery: {},
    Missed Orders: {},

Output Action: `("serve", {"food": "BeefBurger"})`

[Example End]

[Example Begin]

Observation 2:     Remained Timestep: 270,
    Score: 260.0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 1,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 1,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 1,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 1,
                        ('Lettuce', 'Unchopped'): 1,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 1},
            'orders': [{'name': 'BeefLettuceBurger', 'remain_time': 133},
                       {'name': 'BeefLettuceBurger', 'remain_time': 202},
                       {'name': 'BeefBurger', 'remain_time': 233},
                       {'name': 'BeefLettuceBurger', 'remain_time': 300}]},
    Delivery: {'BeefBurger': 20.0},
    Missed Orders: {},


Output Action:  `('assemble', {'food': 'BeefBurger'})`

[Example End]

[Example Begin]

Observation 3:     Remained Timestep: 223,
    Score: 260.0,
    State: {'inventory_other_player': {1: {'name': 'BeefLettuceBurger', 'status': ''}},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 1,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 1,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 1,
                        ('Lettuce', 'Unchopped'): 1,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 1},
            'orders': [{'name': 'BeefLettuceBurger', 'remain_time': 86},
                       {'name': 'BeefLettuceBurger', 'remain_time': 155},
                       {'name': 'BeefBurger', 'remain_time': 186},
                       {'name': 'BeefLettuceBurger', 'remain_time': 253}]},
    Delivery: {},
    Missed Orders: {},

Output Action:  `('serve', {'food': 'BeefLettuceBurger'})`

[Example End]
"""


def get_act_goal_prompt(
    info_input: str,
) -> str:
    return (
        ACT_GOAL_PROMPT
        + f"""\n\

# Input

{info_input}

# OutputFormat

Based on the current game state, considering the remaining time for the orders and the status of all ingredients on the kitchen, decide your next action.
Note that your actions should help advance the orders you’re working on and the game process. Be sure to also consider your previous actions and their outcomes.
Please output a valid action in JSON format.
"""
    )
