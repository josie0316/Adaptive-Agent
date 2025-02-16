MESSAGE_PROMPT = """- Message logs, including those sent from you and the human player. Pay attention that in the message you send: "You" indicates the human player, "Us" indicates the team, "I" indicates the agent (yourself). Note that the human player may not follow the message you send."""
LATEST_MESSAGE_PROMPT = """ and the latest message from human (if any)."""

INFERRED_HUMAN_PROMPT = """\
**Inference of Human Behavior Pattern**.
  - *Your inference* on behavior patterns or tendencies of the human player, *which may not be accurate*."""

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


URGENT_RESPONSE_GOAL_PROMPT = """\
# Instructions

## Goal

Based on these settings, you need to consider how to play the game with your partner to achieve a higher score. The agent will automatically prepare the burger order with the least remaining time. You will receive game history and your task is to respond to urgent situations for improving the performance.

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
**Behavior Guidelines**:
    - The behavior guidelines are the suggestions you have given to the agent based on the game history.
{INFERRED_HUMAN_PROMPT}

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
- 18 empty counters.
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

**Urgent Needs**: `assigned_tasks` are mainly used for urgent needs you have found according to the latest (current) game state{LATEST_MESSAGE_PROMPT}.

# Examples

{FEW_SHOT_EXAMPLE}

# Input

{INPUT}
"""


def get_urgent_response_goal_prompt(
    few_shot_example_prompt: str,
    info_input: str,
    message_prompt: str = "",
    latest_message_prompt: str = "",
    inferred_human_prompt: str = "",
) -> str:
    class PartialFormatter(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    goal_prompt_values = {
        "MESSAGE_PROMPT": message_prompt,
        "INFERRED_HUMAN_PROMPT": inferred_human_prompt,
        "GAME_STATE_EXAMPLE": GAME_STATE_EXAMPLE,
        "ASSIGNED_TASKS_EXAMPLE": ASSIGNED_TASKS_EXAMPLE,
        "LATEST_MESSAGE_PROMPT": latest_message_prompt,
        "FEW_SHOT_EXAMPLE": few_shot_example_prompt,
        "INPUT": info_input,
    }
    return URGENT_RESPONSE_GOAL_PROMPT.format_map(PartialFormatter(goal_prompt_values))


REFLECTION_GOAL_PROMPT = """\
# Instructions

## Goal

Based on these settings, you need to consider how to play the game with your partner to achieve a higher score. The agent will automatically prepare the burger order with the least remaining time. You will receive game history, and your task is to reflect on how to improve performance based on the following information and output reflection for future game playing.

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

**Behavior Guidelines**:
  - The behavior guidelines are the suggestions you have given to the agent based on the game history.

{INFERRED_HUMAN_PROMPT}

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

{GAME_STATE_EXAMPLE}

# Input

{INPUT}
"""


def get_reflection_goal_prompt(
    info_input: str,
    message_prompt: str = "",
    inferred_human_prompt: str = "",
) -> str:
    class PartialFormatter(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    goal_prompt_values = {
        "GAME_STATE_EXAMPLE": GAME_STATE_EXAMPLE,
        "MESSAGE_PROMPT": message_prompt,
        "INFERRED_HUMAN_PROMPT": inferred_human_prompt,
        "INPUT": info_input,
    }
    return REFLECTION_GOAL_PROMPT.format_map(PartialFormatter(goal_prompt_values))


MESSAGE_OUTPUT_FORMAT = """\
```text
Express your intention as message to the human player, for example, what you are planning to do, or what you expect the team to achieve. You should return a text code block as your message.
Be polite, concise and clear, less than 10 words.
Pay attention that this message is sending to human player by agent (yourself), so please use "You" to indicate the human player and use "Us" to indicate the team, use "I" to indicate the agent (yourself). For example, "I will prepare the LettuceBurger" means the agent (yourself) will prepare the LettuceBurger, "We need a Bread" means the team need to prepare a bread.
Note that the human player may not follow the message.
Do not ask the human to do something all the time, especially do not use "you should" or "you can".
You can return an empty string (`""`) here when no message is needed.
```
"""

URGENT_RESPONSE_OUTPUT_FORMAT = """\
# OutputFormat

Please output in the following template:

You should return a text code block as your thought about how to prepare and serve burgers effectively.
```text
Be concise and clear, less than 50 words.
If no urgent responses are needed, return "Things are going well".
Do not directly copy the previous thoughts.
```

{MESSAGE_OUTPUT_FORMAT}

Return a **json** code block representation of the new assigned tasks that the agent will do urgently.
```json
**Pay attention that the agent will automatically prepare the burger order with the least remaining time and you should only assign tasks when changes are necessary.**
You can either keep some of the current assigned tasks if you find them still necessary, or substitute the current assigned tasks with the new ones, i.e., you don't need to include the current assigned tasks in the output.
You should make sure that the completed burgers are served to the customers in time, by letting the agent perform in default mode or adding serving actions. But do not serve the burgers that are not in the order list.
You should return an empty list (`[]`) here when the agent can automatically finish the orders itself and not urgent responses are needed.
Be careful to write correct lambda functions.
Do not directly copy the previous assigned tasks.
The JSON will be used in Python as `eval(json_string)`, so make sure it is in the correct format, e.g., use `True` and `False` instead of `true` and `false`.
```
"""


def get_urgent_response_output_format_prompt(message_output_format: str = "") -> str:
    return URGENT_RESPONSE_OUTPUT_FORMAT.format(MESSAGE_OUTPUT_FORMAT=message_output_format)


HUMAN_INFERENCE_OUTPUT_FORMAT = """\

You should return new **inference on the human player's behavior pattern** in the following code block.
```text
Analyze the past game history and identify patterns or tendencies in the human player's behaviors. Then explain how the agent's policy will be adjusted to coordinate better with the human player.
Here are some suggestions for writing inference:
- What are the human player's preferences in completing orders? For example, whether the human player prefers to complete orders with the least remaining time or orders with the most remaining time? This will help you determine which orders you should focus on to avoid missing any order and to prevent making extra food.
- How does the human player prioritize tasks when multiple orders are pending? For example, whether the human player tends to do order by order or tries to complete multiple orders simultaneously by preparing multiple ingredients in parallel?
- Which processes does the human player prefer to complete first? For example, whether the human player prefers to prepare which ingredients, assemble burgers or serve burgers? This will affect your choices regarding which tasks to prioritize. For example, when human player prefers to preparing ingredients, you choose to serve more dishes can effectively improve team efficiency. When human player prefers to assemble burgers, you can choose to prepare more ingredients and pass on to the counter to meet the requirements of the human player.
- Consider whether there are any patterns between human player's behavior, the current orders that need to be completed, and the ingredients available on the field. For example, humans tend to prepare a large amount of beef when multiple orders for beef burgers are needed. Such implicit patterns can help you adjust your own behavior.{INFER_HUMAN_WITH_SEND_MESSAGE}{INFER_HUMAN_WITH_RECEIVE_MESSAGE}
- How the agent's policy should be adjusted to improve performance? For example, if you believe the ingredients you’ve prepared or the burgers you’ve made are meant for the human player to assemble or serve, you should pass them to the counter to facilitate efficient collaboration.
The inference should be given **based on the game history**.
You should return a text code block. Be concise and clear, less than 100 words.
```
"""

INFER_HUMAN_WITH_SEND_MESSAGE = """\

- How does the human player respond to messages from the agent (you)? You should consider the human's action after receiving message from you to infer whether the human player follows the agent's suggestions, ignores them, or provides feedback on the agent's (your) messages."""

INFER_HUMAN_WITH_RECEIVE_MESSAGE = """\

- What are the propose of human when he/she send a message to you? You should consider the human's action after sending  message to you to infer whether the human player sends requirements or suggestions, or explains his or her actions and plans to the agent (you) through sending messages."""


def get_human_inference_output_format_prompt(
    infer_human_with_send_message: str = "", infer_human_with_receive_message: str = ""
) -> str:
    return HUMAN_INFERENCE_OUTPUT_FORMAT.format(
        INFER_HUMAN_WITH_SEND_MESSAGE=infer_human_with_send_message,
        INFER_HUMAN_WITH_RECEIVE_MESSAGE=infer_human_with_receive_message,
    )


REFLECTION_OUTPUT_FORMAT = """\
# OutputFormat

Please output in parts and in the following template:

You should return new **Behavior Guidelines** in the following code block.
```text
Analyze the past game history and identify areas for improvement or successful strategies. Then explain how the agent's policy will be adjusted based on the reflection.
Here are some suggestions for writing guidelines:
- What leads to the lost of scores, e.g., missed orders and served wrong food, in the past game?
- What leads to the waste of time in the past game?
- How to adjust the agent's policy to save time?
- What are the successful strategies in the past game?
- How to coordinate with the human player to achieve a higher score?
- How the agent's policy should be adjusted to improve performance?
- Why the beef is overcooked? How to avoid overcooking beef?
- Other suggestions for improving the performance of the team.
The guidelines should be given **based on the game history**.
You should return a text code block. Be concise and clear, less than 100 words.
```
{HUMAN_INFERENCE_OUTPUT_FORMAT}"""


def get_reflection_output_format_prompt(human_inference_output_format: str = "") -> str:
    return REFLECTION_OUTPUT_FORMAT.format(HUMAN_INFERENCE_OUTPUT_FORMAT=human_inference_output_format)
