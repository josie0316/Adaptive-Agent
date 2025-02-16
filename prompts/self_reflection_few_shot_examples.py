# template
# {
#     "name": ...,
#     "Situation": ...,
#     "Current Assigned Tasks": ...,
#     "Current Assigned Orders": ...,
#     "Current Behavior Pattern": ...,
#     "Reflection on History & Description of Agent Behavior Modifications": ...,
#     "New Assigned Tasks": ...,
#     "New Assigned Orders": ...,
#     "New Behavior Pattern": ...,
# },
urgent_response_examples = [
    {
        "name": "Fire",
        "Situation": "A piece of beef was accidentally left on the pan for too long and caught fire.",
        "Current Assigned Tasks": [
            "BeefBurger",
            "BeefLettuceBurger",
        ],
        "Current Behavior Pattern": {},
        "Reflection on History & Description of Agent Behavior Modifications": "Given the fire, the immediate need is to extinguish it to prevent further disruption. The agent should prioritize putting out the fire before continuing with any other actions. This can be done by adding a specific assigned task to handle fires.",
        "New Assigned Tasks": [
            ("lambda json_state: json_state['objects'][('Fire', '')] > 0", ("putout_fire", {})),
            "BeefBurger",
            "BeefLettuceBurger",
        ],
        "New Behavior Pattern": {},
    },
    {
        "name": "Urgent LettuceBurger",
        "Situation": "The kitchen team has received a new order for a LettuceBurger, which currently has 80 steps remaining.",
        "Current Assigned Tasks": ["BeefBurger", "BeefLettuceBurger"],
        "Current Behavior Pattern": {},
        "Reflection on History & Description of Agent Behavior Modifications": "Given the new LettuceBurger order with 80 steps remaining, it is crucial to prioritize this order to avoid a delay in service. By adding this order to the assigned tasks and ensuring its timely completion, the agent can avoid losing points.",
        "New Assigned Tasks": ["LettuceBurger", "BeefBurger", "BeefLettuceBurger"],
        "New Behavior Pattern": {},
    },
    ## based on observed history
    {
        "name": "Divide the Labor by Orders",
        "Situation": " The orders are three BeefBurgers and one LettuceBurger. From the game history, you has observed that the human player tends to complete orders sequentially, focusing on one at a time. The human player has already completed the preparation of one beef.",
        "Current Assigned Tasks": [],
        "Current Behavior Pattern": {},
        "Reflection on History & Description of Agent Behavior Modifications": "The agent controlled by me should complete one BeefBurger and one LettuceBurger.",
        "New Assigned Tasks": ["BeefBurger", "LettuceBurger"],
        "New Behavior Pattern": {},
    },
    ## based on current game state and current message
    {
        "name": "Prepare Breads and Plate in Advance",
        "Situation": "The kitchen has received an order for four burgers. In the given history, the human player prepares beef and lettuce but not bread. There are no breads on the counter.",
        "Current Assigned Tasks": [],
        "Current Behavior Pattern": {},
        "Reflection on History & Description of Agent Behavior Modifications": "Given the situation, it is crucial to prepare bread and plate in advance to avoid delays in assembling the burgers. The agent should add prepare breads and pass on them to the center counters.",
        "New Assigned Tasks": [
            (
                "lambda json_state: json_state['objects'][('Bread', '')] < 2",
                ("prepare", {"food": "Bread", "plate": True}),
            ),
            ("lambda json_state: True", ("pass_on", {"thing": "Bread"})),
            (
                "lambda json_state: json_state['objects'][('Bread', '')] < 2",
                ("prepare", {"food": "Bread", "plate": True}),
            ),
            ("lambda json_state: True", ("pass_on", {"thing": "Bread"})),
        ],
        "New Behavior Pattern": {},
    },
]


def example_to_str(example: dict) -> str:

    example_str = "[Example Begin]\n"
    example_str += f"""Situation:
```text
{example['Situation']}
```\n"""
    if example["Current Assigned Tasks"]:
        example_str += f"""Current Assigned Tasks:
```json
{str(example["Current Assigned Tasks"])}
```\n"""

    if example["Current Behavior Pattern"]:
        example_str += f"""Current Behavior Pattern:
```json
{str(example["Current Behavior Pattern"])}
```\n"""

    example_str += f"""Reflection on History & Description of Modifications:
```text
{example['Reflection on History & Description of Agent Behavior Modifications']}
```\n"""

    if example["New Assigned Tasks"]:
        example_str += f"""New Assigned Tasks:
```json
{str(example["New Assigned Tasks"])}
```\n"""

    if example["New Behavior Pattern"]:
        example_str += f"""New Behavior Pattern:
```json
{str(example["New Behavior Pattern"])}
```\n"""

    example_str += "[Example End]\n"

    return example_str
