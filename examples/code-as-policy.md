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
    Preparing `("Beef", "Well-cooked")`: Get a `("Beef", "Fresh")` and cook it into a `("Beef", "In-progress")` and then a `("Beef", "Well-cooked")`. Pay attention to avoid overcooking it, which will result in a `("Beef", "Overcooked")` and a `("Fire", "")` in the pan.
    - `("prepare", {"food": "Beef", "plate": True})`
    - `("prepare", {"food": "Beef", "plate": False})`
    Preparing `("Lettuce", "Chopped")`: Get a `("Lettuce", "Unchopped")` and chop it into a `("Lettuce", "Chopped")`.
    - `("prepare", {"food": "Lettuce", "plate": True})`
    - `("prepare", {"food": "Lettuce", "plate": False})`
    Preparing `("Bread", "")`: Get a `("Bread", "")` and put it on the counter or in a plate.
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

Based on these settings, you need to consider how to play the game with your partner to achieve a higher score. The agent will automatically prepare the burger order with the least remaining time. You will receive game history and your task is to update the `Assigned Tasks' and output them as JSON in a code block, improving the performance

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
**Current Assigned Tasks**:
    - The current actions and orders you assigned to the agent that need to be done urgently.
**Behavior Guidelines**:
    - The behavior guidelines are the suggestions you have given to the agent based on the game history.
**Inference of Human Behavior Pattern**.
    - Any observed patterns or tendencies in the human player's behaviors.

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

3. **Inventory of the Other Player**:
    - The `inventory_other_player` dictionary records the objects held by the other player. Each entry maps `other_agent_id` to a tuple of `(object_name, object_status)`.
    - This helps in understanding what the other player is currently holding, allowing for better coordination.

#### Example Game State

Now I will show you an game state example. In this example, there are
- 1 fresh beef, 1 in-progress beef, and 1 overcooked beef. No well-cooked beef.
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


### Assigned Tasks

In this game, the `assigned tasks` are the actions and orders which you assign to the agent that need to **prioritize and complete urgently**.

Assigned tasks can be actions with pre-conditions and order names.

#### Assigned Actions

Assigned tasks can contains pairs of preconditions and actions. Each pair specifies a condition that must be met and the corresponding action that should be taken when the condition is true. Here's a breakdown of what each element means:

1. **Precondition**:
    - A lambda function that takes `json_state` as an input and returns a boolean value.
    - It indicates whether a specific condition is met in the current game state.
    - For example: When you want to detect whether there are fewer than 3 well-cooked or in-process beefs, you can use `"lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] + json_state['objects'][('Beef', 'In-progress')] < 3"`.

2. **Action**:
    - A tuple containing the action name and the action arguments.
    - The action name is a string, and the action arguments are provided as a dictionary.

#### Assigned Orders

The `assigned_tasks` can also contains the names of the orders that need to be completed in sequence.

- Each order (element) in this list is an order name in string.

#### Example Assigned Tasks

Now I will show you an example of an assigned tasks below.
In this example, the agent do the following tasks:
- prepare beef if the number of well-cooked or in-process beefs are fewer than the number of requirements.
- prepare a BeefBurger.
- prepare a LettuceBurger.

```json
[
    (
        "lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] + json_state['objects'][('Beef', 'In-progress')] < sum(order['name'] == 'BeefBurger' or order['name'] == 'BeefLettuceBurger' for order in json_state['orders'])", ("prepare", {"food": "Beef", "plate": False})
    ),
    "BeefBurger",
    "LettuceBurger"
]
```


Note that `assigned_tasks` will be executed in sequence **only once**, i.e., the actions will be executed if the preconditions are met and the orders will be prepared. If you want to prioritize some tasks, you can assign them in the head of `assigned_tasks`. Please pay attention to put the most urgent tasks in the head of the list.

**Urgent Needs**: `assigned_tasks` are mainly used for urgent needs you have found according to the latest (current) game state and the latest message from human (if any).

# Examples

<example>
Situation:
```json
A piece of beef was accidentally left on the pan for too long and caught fire.
```
Current Assigned Tasks:
```json
['BeefBurger', 'BeefLettuceBurger']
```
Reflection on History & Description of Modifications:
```json
Given the fire, the immediate need is to extinguish it to prevent further disruption. The agent should prioritize putting out the fire before continuing with any other actions. This can be done by adding a specific assigned task to handle fires.
```
New Assigned Tasks:
```json
[("lambda json_state: json_state['objects'][('Fire', '')] > 0", ('putout_fire', {})), 'BeefBurger', 'BeefLettuceBurger']
```
</example>

<example>
Situation:
```json
 The orders are three BeefBurgers and one LettuceBurger. From the game history, you has observed that the human player tends to complete orders sequentially, focusing on one at a time. The human player has already completed the preparation of one beef.
```
Reflection on History & Description of Modifications:
```json
The agent controlled by me should complete one BeefBurger and one LettuceBurger.
```
New Assigned Tasks:
```json
['BeefBurger', 'LettuceBurger']
```
</example>

<example>
Situation:
```json
The kitchen currently has two pending orders for LettuceBurgers and two for BeefBurgers, and there are two Chopped Lettuce and two Well-cooked Beef. The human player sends a message saying, 'We need Lettuce'
```
Reflection on History & Description of Modifications:
```json
Given the human player's request to prepare more lettuce, despite already having enough, the agent must carefully balance the need to acknowledge the human player's input while maintaining efficient workflow. The agent should avoid unnecessary actions and focus on completing the current orders. No changes will be made, as the kitchen's needs are already satisfied
```
</example>

<example>
Situation:
```json
The kitchen team has received a new order for a LettuceBurger, which currently has 80 steps remaining.
```
Current Assigned Tasks:
```json
['BeefBurger', 'BeefLettuceBurger']
```
Reflection on History & Description of Modifications:
```json
Given the new LettuceBurger order with 80 steps remaining, it is crucial to prioritize this order to avoid a delay in service. By adding this order to the assigned tasks and ensuring its timely completion, the agent can avoid losing points.
```
New Assigned Tasks:
```json
['LettuceBurger', 'BeefBurger', 'BeefLettuceBurger']
```
</example>

<example>
Situation:
```json
The kitchen currently has two pending orders for LettuceBurgers and two for BeefBurgers. The human player has sent a message saying, 'We need Beef.'
```
Reflection on History & Description of Modifications:
```json
Given the human player's message, it is crucial to prioritize preparing beef. The agent must adjust the assigned Tasks to include preparing beef to ensure that BeefBurgers can be completed efficiently.
```
New Assigned Tasks:
```json
[("lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] + json_state['objects'][('Beef', 'In-progress')] < 2", ('prepare', {'food': 'Beef'})), ("lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] + json_state['objects'][('Beef', 'In-progress')] < 2", ('prepare', {'food': 'Beef'}))]
```
</example>


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
    Message: {},


Current Assigned Tasks:
```json
[]
```
Current Behavior Guidelines:
```json

```

Inferred Human Behavior:


# OutputFormat

Please output in two parts and in the following template:


```text
You should return a text code block as your thought. Be concise and clear, less than 20 words. If no urgent responses are needed, return "Things are going well".
```

```text
Express your intention as message to the human player, for example, what you are planning to do, what you expect the human player to do, or what you expect the team to achieve. You should return a text code block as your thought.
Be polite, concise and clear, less than 15 words.
Pay attention that this message is show to human player, so use "You" to indicate the human player and use "Us" to indicate the team, use "I" to indicate your agent. For example, "I will prepare the lettuce burger", "You can prepare the beef" or "We should focus on the BeefLettuceBurger".
You can return an empty string (`""`) here when no message is needed.
```


```json
A JSON representation of the new assigned tasks that the agent will do urgently.
**Pay attention that the agent will automatically prepare the burger order with the least remaining time and you should only assign tasks when changes are necessary.**
You can substitute the current assigned tasks with the new ones, i.e., you don't need to include the current assigned tasks in the output.
You should make sure that the completed burgers are served to the customers in time, by letting the agent perform in default mode or adding serving actions. But do not serve the burgers that are not in the order list.
You should return an empty list (`[]`) here when the agent can automatically finish the orders itself and not urgent responses are needed.
Be careful to write correct lambda functions.
The JSON will be used in Python as `eval(json_string)`, so make sure it is in the correct format, e.g., use `True` and `False` instead of `ture` and `flase`.
```

Output:

```text
I will prepare the LettuceBurger and serve it promptly.
```

```text
You can prepare the Beef to help us complete more orders.
```

```json
[
    ("lambda json_state: json_state['objects'][('Lettuce', 'Chopped')] == 1", ("serve", {"food": "LettuceBurger"})),
    ("lambda json_state: json_state['objects'][('Beef', 'Fresh')] == 0", ("prepare", {"food": "Beef", "plate": False}))
]
```
