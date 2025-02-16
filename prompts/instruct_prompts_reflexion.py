MESSAGE_PROMPT = """- Message logs, including those sent from you and the human player. Pay attention that in the message you send: "You" indicates the human player, "Us" indicates the team, "I" indicates the agent (yourself). Note that the human player may not follow the message you send."""
LATEST_MESSAGE_PROMPT = """ and the latest message from human (if any)."""

GAME_STATE_EXAMPLE = """\
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
    ],
    "inventory_other_player": {
        "player_1": ("Plate", "Empty"),
    }
}
```
"""

ASSIGNED_TASKS_EXAMPLE = """\
```json
[
    (
        "lambda json_state: json_state['objects'][('Beef', 'Well-cooked')] + json_state['objects'][('Beef', 'In-progress')] < sum(order['name'] == 'BeefBurger' or order['name'] == 'BeefLettuceBurger' for order in json_state['orders'])", ("prepare", {"food": "Beef", "plate": False})
    ),
    "BeefBurger",
    "LettuceBurger"
]
```
"""


REFLECTION_REACT_GOAL_PROMPT = """\
# Instructions

## Goal

Based on these settings, you need to consider how to play the game with your partner to achieve a higher score. Your decision-making process should consist of interleaving Observation, Thought and Action steps. Thought can reason about the current situation. Observation consists of the following information.

## Input Information

**Game History**:
    - A sequence of game scenes that have occurred in the past. Each game scene is consisted of:
        - Remained Timestep: The remained timestep of the game.
        - Score: The current score of the game.
        - Game State: The occurrences of objects, orders, and other players' inventories.
        - Action: Actions taken by your agent and the human-controlled agent.
        - Delivery: The food that have been delivered and the corresponding obtained score.
        - Missed Orders: The orders that have not been completed in time and the obtained punished score.
        {MESSAGE_PROMPT}
**Current Assigned Tasks**:
    - The current actions and orders you assigned to the agent that need to be done urgently.

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

Now I will show you a game state example. In this example, there are
- 1 fresh beef, 1 in-progress beef, and 1 overcooked beef. No well-cooked beef.
- 3 unchopped lettuce and 1 chopped lettuce.
- 4 bread prepared in advance.
- No assembled BeefLettuce, BeefBurgers, or BeefLettuceBurgers, but there is 1 LettuceBurger ready.
- 2 empty plates on counters.
- 18 empty counters.
- 1 fire extinguisher and no active fire.
- 2 orders pending: a BeefBurger with 30 seconds remaining and a LettuceBurger with 45 seconds remaining.
- Player 1 holding an empty plate.

Note that you will only receive the json below:

{GAME_STATE_EXAMPLE}

### Assigned Tasks

In this game, the `assigned tasks` are the actions and orders which you assign to the agent that need to **prioritize and complete urgently**.

Assigned tasks can be actions with pre-conditions, and order names.

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

Now I will show you an example of assigned tasks below. In this example, the agent do the following tasks:
- prepare beef if the number of well-cooked or in-process beefs are fewer than the number of requirements.
- prepare a BeefBurger.
- prepare a LettuceBurger.

{ASSIGNED_TASKS_EXAMPLE}

Note that `assigned_tasks` will be executed in sequence **only once**, i.e., the actions will be executed if the preconditions are met and the orders will be prepared. If you want to prioritize some tasks, you can assign them in the head of `assigned_tasks`. Please pay attention to put the most urgent tasks in the head of the list.

**Urgent Needs**: `assigned_tasks` are mainly used for urgent needs you have found according to the latest (current) game state.

# Examples

{FEW_SHOT_EXAMPLE}

# Input

{INPUT}

# OutputFormat

Please output in the following template:

Based on a previous reasoning, you have done a self refection. The reflection includes the diagnosis of a possible reason for failure and devises a new, concise, high level plan that aims to mitigate the same failure.
Considering the reflection and current situation, you should return a text code block as your thought about how to prepare and serve burgers effectively.
```text
Be concise and clear, less than 50 words.
If no urgent responses are needed, return "Things are going well".
Do not directly copy the previous thoughts.
```

Your action should be a **json** code block representation of the new assigned tasks that the agent will do urgently.
```json
You can either keep some of the current assigned tasks if you find them still necessary, or substitute them with the new ones, i.e., you don't have to include the current assigned tasks in the output.
You should make sure that the completed burgers are served to the customers in time, by adding serving actions. But do not serve the burgers that are not in the order list.
You should return enough assigned tasks to keep the agent busy.
Be careful to write correct lambda functions.
Do not directly copy the previous assigned tasks.
The JSON will be used in Python as `eval(json_string)`, so make sure it is in the correct format, e.g., use `True` and `False` instead of `true` and `false`.
```
"""

REFLECTION_GOAL_PROMPT = """
# Instructions

## Goal

Based on these settings, you need to consider how to play the game with your partner to achieve a higher score. Your decision-making process should consist of interleaving Observation, Thought and Action steps. Thought can reason about the current situation. Observation consists of the following information.

## Input Information

**Game History**:
    - A sequence of game scenes that have occurred in the past. Each game scene is consisted of:
        - Remained Timestep: The remained timestep of the game.
        - Score: The current score of the game.
        - Game State: The occurrences of objects, orders, and other players' inventories.
        - Action: Actions taken by your agent and the human-controlled agent.
        - Delivery: The food that have been delivered and the corresponding obtained score.
        - Missed Orders: The orders that have not been completed in time and the obtained punished score.
        {MESSAGE_PROMPT}
**Current Assigned Tasks**:
    - The current actions and orders you assigned to the agent that need to be done urgently.

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

Now I will show you a game state example. In this example, there are
- 1 fresh beef, 1 in-progress beef, and 1 overcooked beef. No well-cooked beef.
- 3 unchopped lettuce and 1 chopped lettuce.
- 4 bread prepared in advance.
- No assembled BeefLettuce, BeefBurgers, or BeefLettuceBurgers, but there is 1 LettuceBurger ready.
- 2 empty plates on counters.
- 1 fire extinguisher and no active fire.
- 2 orders pending: a BeefBurger with 30 seconds remaining and a LettuceBurger with 45 seconds remaining.
- Player 1 holding an empty plate.

Note that you will only receive the json below:

{GAME_STATE_EXAMPLE}

### Assigned Tasks

In this game, the `assigned tasks` are the actions and orders which you assign to the agent that need to **prioritize and complete urgently**.

Assigned tasks can be actions with pre-conditions, and order names.

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

Now I will show you an example of assigned tasks below. In this example, the agent do the following tasks:
- prepare beef if the number of well-cooked or in-process beefs are fewer than the number of requirements.
- prepare a BeefBurger.
- prepare a LettuceBurger.

{ASSIGNED_TASKS_EXAMPLE}

Note that `assigned_tasks` will be executed in sequence **only once**, i.e., the actions will be executed if the preconditions are met and the orders will be prepared. If you want to prioritize some tasks, you can assign them in the head of `assigned_tasks`. Please pay attention to put the most urgent tasks in the head of the list.

**Urgent Needs**: `assigned_tasks` are mainly used for urgent needs you have found according to the latest (current) game state.

# Examples

{FEW_SHOT_EXAMPLE}

# Input

{INPUT}

# OutputFormat

Based on a previous reasoning, you should improve based on self refection. Diagnose a possible reason for failure and devise a new, concise, high level plan that aims to mitigate the same failure. Use complete sentences.
You should return a text code block as your reflection when you meet the following failure situations: 1)Fire, 2)Missing Order, 3)Loss Score, 4)Other unexpected situations.
```text
Be concise and clear, less than 100 words.
If no reflection is needed, return "Things are going well".
Do not directly copy the previous reflection.
```
"""


def get_reflection_react_goal_prompt(
    few_shot_example_prompt: str,
    info_input: str,
    message_prompt: str = "",
    latest_message_prompt: str = "",
) -> str:
    class PartialFormatter(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    goal_prompt_values = {
        "MESSAGE_PROMPT": message_prompt,
        "GAME_STATE_EXAMPLE": GAME_STATE_EXAMPLE,
        "ASSIGNED_TASKS_EXAMPLE": ASSIGNED_TASKS_EXAMPLE,
        "LATEST_MESSAGE_PROMPT": latest_message_prompt,
        "FEW_SHOT_EXAMPLE": few_shot_example_prompt,
        "INPUT": info_input,
    }
    return REFLECTION_REACT_GOAL_PROMPT.format_map(PartialFormatter(goal_prompt_values))


def get_reflection_goal_prompt(
    few_shot_example_prompt: str,
    info_input: str,
    message_prompt: str = "",
    latest_message_prompt: str = "",
) -> str:
    class PartialFormatter(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    goal_prompt_values = {
        "MESSAGE_PROMPT": message_prompt,
        "GAME_STATE_EXAMPLE": GAME_STATE_EXAMPLE,
        "ASSIGNED_TASKS_EXAMPLE": ASSIGNED_TASKS_EXAMPLE,
        "LATEST_MESSAGE_PROMPT": latest_message_prompt,
        "FEW_SHOT_EXAMPLE": few_shot_example_prompt,
        "INPUT": info_input,
    }
    return REFLECTION_GOAL_PROMPT.format_map(PartialFormatter(goal_prompt_values))
