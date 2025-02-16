TASK_DESC = """\
As a player in a collaborative cooking game, you are working with a human player to complete hamburger orders.
Focus on cooperation, player engagement, fulfillment, and score accrual.
"""


def get_task_description():
    return TASK_DESC


MESSAGE_SYSTEM_PROMPT_ONLY_LLM = """\
### Message System

In this game, only you send messages to the human player, in your messages, you will explain your plans and actions. The human player will not send any messages to you.
"""
MESSAGE_SYSTEM_PROMPT_ONLY_HUMAN = """\
### Message System

In this game, only human player sends messages to you. In these messages, they will indicate the team's current tasks and priorities. You will not send any messages to the human player.

**Use the information in these messages to achieve a higher score, rather than simply following the instructions.**
"""
MESSAGE_SYSTEM_PROMPT_BOTH = """\
### Message System

In this game, both you and the human player can send messages to each other. You will explain your plans and actions in your messages, while the human player will indicate the team's current tasks and priorities in their messages.

**Use the information in these messages to achieve a higher score, rather than simply following the instructions.**
"""

GAME_SETTINGS = """\
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

- **Pass On Action**: Used to pass something to your partner by putting it on the central counter.
  - `("pass_on", {"thing": "Plate"})`
  - `("pass_on", {"thing": "Bread"})`
  - `("pass_on", {"thing": "Lettuce", "thing_status": "Chopped"})`
  - `("pass_on", {"thing": "Lettuce", "thing_status": "Unchopped"})`
  - `("pass_on", {"thing": "Beef", "thing_status": "Well-cooked"})`
  - `("pass_on", {"thing": "Beef", "thing_status": "Fresh"})`
  - `("pass_on", {"thing": "BeefLettuce"})`
  - `("pass_on", {"thing": "BeefBurger"})`
  - `("pass_on", {"thing": "LettuceBurger"})`
  - `("pass_on", {"thing": "BeefLettuceBurger"})`
  - `("pass_on", {"thing": "FireExtinguisher"})`

- **Serve Actions**: Used to serve the assembled burgers to the customer.
  - `("serve", {"food": "BeefBurger"})`
  - `("serve", {"food": "LettuceBurger"})`
  - `("serve", {"food": "BeefLettuceBurger"})`

- **Put Out Fire Action**: Used to pick up the fire extinguisher and put out the fire on the pan when the `Beef` is overcooked and catches fire.
  - `("putout_fire", {})`

- **Clean A Counter Action**: Used to clean a counter by dropping all objects on it to the trash can.
  - `("clean_a_counter", {})`

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
"""


def get_urgent_response_game_prompt(message_system_prompt):
    return f"{GAME_SETTINGS}\n{message_system_prompt}"


def get_reflection_game_prompt(message_system_prompt):
    return f"{GAME_SETTINGS}\n{message_system_prompt}"
