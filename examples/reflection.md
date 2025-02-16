Input:

# Game Introduction

## Game Scene

The game environment is set in a kitchen, designed for a collaborative cooking challenge. The layout includes a central counter area surrounded by various stations and essential elements for gameplay. Here's a detailed breakdown of the scene:

- **Central Counter Area**: The central space has a counter where ingredients can be placed temporarily for efficient workflow.
- **Ingredient Stations**: Distribution stations for picking up `Lettuce`, `Beef` and `Bread`.
- **Cooking and Preparation Tools**:
  - **Pans**: for cooking `Beef`.
  - **Cutboards**: for preparing `Lettuce`.
- **Plate Station**: for picking up empty plates.
- **Fire Extinguisher**: for extinguishing fires and can be moved.
- **Serving Area**: for serving orders.

You are controlling one of the two chefs in the kitchen, and your goal is to work together with your partner to fulfill customer orders efficiently and accurately by writing codes to improve your policies in the game.

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

- **Pass On Action**: Used to pass a plate to your partner by putting it on the central counter.
  - `("pass_on", {"thing": "Plate"})`

- **Serve Actions**: Used to serve the assembled burgers to the customer.
  - `("serve", {"food": "BeefBurger"})`
  - `("serve", {"food": "LettuceBurger"})`
  - `("serve", {"food": "BeefLettuceBurger"})`

- **Put Out Fire Action**: Used to pick up the fire extinguisher and put out the fire on the pan when the `Beef` is overcooked and catches fire.
  - `("putout_fire", {})`

### Cookbook

In this collaborative kitchen game, the goal is to prepare and serve burgers efficiently to earn points. The game features three types of burgers: `LettuceBurger`, `BeefBurger`, and `BeefLettuceBurger`. Here are the rules and how the actions fit into the gameplay:

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

### Message System

In this game, both you and the human player can send messages to each other. You will explain your plans and actions in your messages, while the human player will indicate the team's current tasks and priorities in their messages.

**Use the information in these messages to achieve a higher score, rather than simply following the instructions.**

# Instructions

## Goal

Based on these settings, you need to consider how to play the game with your partner to achieve a higher score. The agent will automatically prepare the burger order with the least remaining time. You will receive game history, and your task is to reflect on how to improve performance based on the following information and output **Behavior Guidelines** for future game playing as JSON in a text code block.

## Input Information

**Game History**:
  - A sequence of game scenes that have occurred in the past. Each game scene is consisted of:
    - Remained Timestep: The remained timestep of the game.
    - Score: The current score of the game.
    - Game State: The occurrences of objects, orders, and other players' inventories.
    - Action: Actions taken by your agent and the human-controlled agent.
    - Delivery: The food that have been delivered and the corresponding obtained score.
    - Missed Orders: The orders that have not been completed in time and the obtained punished score.
    - Message logs, including those sent from you and the human player.

**Behavior Guidelines**:
  - The behavior guidelines are the suggestions you have given to the agent based on the game history.

**Inference of Human Behavior Pattern**:
  - Any observed patterns or tendencies in the human player's behaviors.

### Game State

The current state of the game includes various details. Here's a detailed description based on the provided structure:

1. **Objects**:
    - The `objects` dictionary records the number of objects with different statuses. Each entry is a tuple of `(object_name, object_status)` mapped to `object_number`.
    - For example:
        - `("Beef", "Well-cooked") : 2` indicates that there are 2 well-cooked beef.

2. **Orders**:
    - The `orders` list contains the current orders that need to be completed. Each order is a dictionary with:
        - `name`: The name of the order, which can be `BeefBurger`, `LettuceBurger`, or `BeefLettuceBurger`.
        - `remain_time`: The remaining time to complete the order, with smaller remaining time indicating higher urgency.

3. **Inventory of the Other Player**:
    - The `inventory_other_player` dictionary records the objects held by the other player. Each entry maps `other_agent_id` to a tuple of `(object_name, object_status)`.
    - This helps in understanding what the other player is currently holding, allowing for better coordination.

#### Example Game State

Now I will show you an game state example. In this example, there are
- 2 fresh beef, 1 in-progress beef, and 1 overcooked beef. No well-cooked beef.
- 3 unchopped lettuce and 1 chopped lettuce.
- 4 bread prepared in advance.
- No assembled BeefLettuce, BeefBurgers, or BeefLettuceBurgers, but there is 1 LettuceBurger ready.
- 2 empty plates on counters.
- 1 fire extinguisher and no active fire.
- 2 orders pending: a BeefBurger with 30 seconds remaining and a LettuceBurger with 45 seconds remaining.
- Player 1 holding an empty plate.

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
    "orders": [
        {
            "name": "BeefBurger",
            "remain_time": 30
        },
        {
            "name": "LettuceBurger",
            "remain_time": 45
        }
    ],
    "inventory_other_player": {
        "player_1": ("Plate", "Empty"),
    }
}
```


# INPUT

History:
Scene 1:
    Remained Timestep: 1000,
    Score: 0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 0,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 0,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 0,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'LettuceBurger', 'remain_time': 200}]},
    Action: {'You': ('prepare', {'food': 'Lettuce', 'plate': False})},
    Delivery: {},
    Missed Orders: {},
    Message: {},

Scene 2:
    Remained Timestep: 984,
    Score: 0.0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 0,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 0,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 1,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'LettuceBurger', 'remain_time': 184}]},
    Action: {'You': ('assemble', {'food': 'LettuceBurger'})},
    Delivery: {},
    Missed Orders: {},
    Message: {'You': 'You can prepare the Beef to help us complete more orders.'},

Scene 3:
    Remained Timestep: 954,
    Score: 0.0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 0,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 0,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 0,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 1,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'LettuceBurger', 'remain_time': 154},
                       {'name': 'BeefBurger', 'remain_time': 229}]},
    Action: {'You': ('prepare', {'food': 'Beef', 'plate': False})},
    Delivery: {},
    Missed Orders: {},
    Message: {},

Scene 4:
    Remained Timestep: 942,
    Score: 0.0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 1,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 0,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 0,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 1,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'LettuceBurger', 'remain_time': 142},
                       {'name': 'BeefBurger', 'remain_time': 217},
                       {'name': 'LettuceBurger', 'remain_time': 192}]},
    Action: {'You': ('serve', {'food': 'LettuceBurger'})},
    Delivery: {},
    Missed Orders: {},
    Message: {'You': 'You can prepare the Beef to help us complete more orders.'},

Scene 5:
    Remained Timestep: 929,
    Score: 15.0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 1,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 0,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 0,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'BeefBurger', 'remain_time': 204},
                       {'name': 'LettuceBurger', 'remain_time': 179},
                       {'name': 'LettuceBurger', 'remain_time': 200}]},
    Action: {'You': ('prepare', {'food': 'Lettuce', 'plate': False})},
    Delivery: {'LettuceBurger': 15.0},
    Missed Orders: {},
    Message: {'You': 'You can prepare the beef to help us complete more orders.'},

Scene 6:
    Remained Timestep: 907,
    Score: 15.0,
    State: {'inventory_other_player': {1: None},
            'objects': {('Beef', 'Fresh'): 0,
                        ('Beef', 'In-progress'): 0,
                        ('Beef', 'Overcooked'): 0,
                        ('Beef', 'Well-cooked'): 1,
                        ('BeefBurger', ''): 0,
                        ('BeefLettuce', ''): 0,
                        ('BeefLettuceBurger', ''): 0,
                        ('Bread', ''): 0,
                        ('Fire', ''): 0,
                        ('FireExtinguisher', ''): 1,
                        ('Lettuce', 'Chopped'): 1,
                        ('Lettuce', 'Unchopped'): 0,
                        ('LettuceBurger', ''): 0,
                        ('Plate', 'Empty'): 0},
            'orders': [{'name': 'BeefBurger', 'remain_time': 182},
                       {'name': 'LettuceBurger', 'remain_time': 157},
                       {'name': 'LettuceBurger', 'remain_time': 178},
                       {'name': 'LettuceBurger', 'remain_time': 182}]},
    Action: {'You': ('assemble', {'food': 'BeefBurger'})},
    Delivery: {},
    Missed Orders: {},
    Message: {},


Current Behavior Guidelines:
```json

```

Inferred Human Behavior:


# OutputFormat

Please output in parts and in the following template:

```text
 some **Behavior Guidelines** for improving performance.
Analyze the past game history and identify areas for improvement or successful strategies. Then explain how the agent's policy will be adjusted based on the reflection.
Here are some suggestions for writing guidelines:
- What leads to the lost of scores, e.g., missed orders and served wrong food, in the past game?
- What leads to the waste of time in the past game?
- What are the successful strategies in the past game?
- How to coordinate with the human player to achieve a higher score?
The guidelines should be given **based on the game history**.
You should return a text code block. Be concise and clear, less than 100 words.
```

```text
Here are some **inference on the human player's behavior pattern**.
Analyze the past game history and identify patterns or tendencies in the human player's behaviors. Then explain how the agent's policy will be adjusted to coordinate better with the human player.
Here are some suggestions for writing inference:
- What are the human player's preferences in completing orders? For example, whether the human player tends to complete BeefBurgers first, LettuceBurgers first, or BeefLettuceBurgers first?
- How does the human player prioritize tasks when multiple orders are pending? For example, whether the human player focuses on one order at a time or tries to complete multiple orders simultaneously by preparing multiple ingredients in parallel?
- Which processes does the human player prefer to complete first? For example, whether the human player prefers to prepare ingredients, assemble burgers or serve burgers?
- How does the human player respond to messages from the agent (you)? For example, whether the human player follows the agent's suggestions, ignores them, or provides feedback on the agent's (your) messages?
- How does the human player send messages to the agent (you)? For example, whether the human player provides requirements or suggestions, or explains his or her actions and plans to the agent (you) through sending messages?
```
The inference should be given **based on the game history**.
You should return a text code block. Be concise and clear, less than 100 words.



Output:

```text
Here are some **Behavior Guidelines** for improving performance.
To avoid score loss, prioritize completing orders with the least remaining time, especially focusing on preparing necessary ingredients promptly. Minimize time waste by coordinating actions with the human player, such as passing plates when needed. Successful strategies include assembling burgers as soon as ingredients are ready and serving completed orders quickly. Enhance communication to ensure both players are aligned on tasks, especially when multiple orders are pending.

```

```text
Here are some **inference on the human player's behavior pattern**.
The human player tends to focus on completing LettuceBurgers first, as seen in multiple actions taken towards that order. They prioritize preparing ingredients before assembling burgers, often responding positively to suggestions about preparing beef. The human player appears to prefer completing one order at a time rather than multitasking. They send messages that indicate their focus on specific tasks, which can be leveraged for better coordination in future rounds.
```
