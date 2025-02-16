import asyncio
import base64
import json
import os
import time

import cv2
import yaml
from markdown import markdown
from quart import Quart, jsonify, request, websocket

from coop_marl.controllers import MultiController
from coop_marl.envs.overcooked.overcooked_maker import OvercookedMaker

# from coop_marl.runners.runners import PlayRunner
from coop_marl.utils import Arrdict, create_parser, parse_args

MAX_INFO_LENGTH = 10

example_instruction = [
    "fetch LettuceStation",
    "drop Dustbin",
    "fetch BeefStation",
    "put_onto Pan",
    "fetch PlateStation",
    "plate Pan",
]


def instruction_generator():
    yield from example_instruction


generator = instruction_generator()


def get_design_instruction(message):
    res = next(generator)
    return res


def get_human_input_instruction(message):
    res = input(message)
    return res


AGENT_ID = 0
MAX_GAME = 6
MAX_AGENT = MAX_GAME * 2

EXPERIMENT_TYPE = 0

TYPE_TO_NAME = {0: "HA", 1: "H", 2: "A", 3: "N"}

INSTRUCTIONS = {
    1: "LettuceBurger",
    2: "BeefBurger",
    3: "BeefLettuceBurger",
    4: "Lettuce",
    5: "Beef",
    6: "Bread",
    7: "Plate",
    8: "Serve",
    9: "Fire",
}

FEEDBACK = {1: "Good Job!", 2: "Need Improvement"}

questionnaire_savepath = "./questionnaire"
traj_savepath = "./traj"

app = Quart(__name__)

# socketio = SocketIO(app)

args, conf, env_conf, trainer = parse_args(create_parser())
reg_env_name = env_conf.name
del env_conf["name"]
envs = [OvercookedMaker(**env_conf, display=True) for _ in range(MAX_GAME)]
[env.reset() for env in envs]

action_spaces = envs[0].action_spaces
control_agents = envs[0].players
controllers = [MultiController(action_spaces) for _ in range(MAX_GAME)]

num_episodes = 1
render_mode = "rgb_array"

status = [True for _ in range(MAX_GAME)]
actions = [0 for _ in range(MAX_AGENT)]
instructions = [0 for _ in range(MAX_AGENT)]
feedbacks = [0 for _ in range(MAX_AGENT)]
connection = [False for _ in range(MAX_AGENT)]
refresh = False

state = [None for _ in range(MAX_GAME)]
updated = [False for _ in range(MAX_AGENT)]
traj_infos = [None for _ in range(MAX_GAME)]

globalstate = False

traj_names = ["" for _ in range(MAX_GAME)]


agent_infos = [
    ("make LettuceBurger", "prepare Lettuce"),
    ("make BeefBurger", "assemble BeefBurger"),
    ("make BeefBurger", "sever BeefBurger"),
    ("make BeefBurger", "prepare Beef"),
    ("make BeefBurger", "prepare Lettuce"),
    ("make BeefBurger", "prepare Tomato"),
]


def update_info_list(info_list, character, new_info, timestep):
    length = len(info_list)
    if length > MAX_INFO_LENGTH:
        info_list.pop(0)
    if type(new_info) == str:
        info_list.append((character, new_info, timestep))
    else:
        info_list.append((character, new_info[0], new_info[1], timestep))
    return info_list


def update_agent_info(info_list, new_info, timestep):
    length = len(info_list)
    if length > MAX_INFO_LENGTH:
        info_list.pop(0)
    info_list.append(("agent", new_info[0], new_info[1], timestep))
    return info_list


async def startgame(id):
    print(f"startgame {id}")
    env = envs[id]
    controller = controllers[id]
    dummy_decision = controller.get_prev_decision_view()

    while True:
        traj_infos[id] = {"t": [], "score": [], "action": []}
        outcome = env.reset()
        frame = env.render(mode=render_mode)
        data = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        data = cv2.imencode(".png", data)[1]
        data = base64.b64encode(data.tobytes()).decode("utf8")
        info_list = []
        state[id] = {"frame": data, "time": 1000, "score": 0, "info_list": info_list}
        updated[id * 2] = True
        updated[id * 2 + 1] = True
        traj_infos[id]["t"].append(0)
        traj_infos[id]["score"].append(0)
        print("game reset")
        while True:
            if connection[id * 2] and connection[id * 2 + 1]:
                break
            await asyncio.sleep(1 / 4)

        while True:
            print(id, "\n")
            decision = Arrdict({p: dummy_decision[p] for p in outcome})
            inp = Arrdict(data=outcome, prev_decision=decision)
            decision = controller.select_actions([actions[id * 2], actions[id * 2 + 1]], inp)
            traj_infos[id]["action"].append([actions[id * 2], actions[id * 2 + 1]])
            print(decision)
            actions[id * 2] = 0
            actions[id * 2 + 1] = 0

            # instructions[id * 2] = 0
            # instructions[id * 2 + 1] = 0
            transition = Arrdict(inp=inp, decision=decision)

            # env step
            outcome, info = env.step(decision)
            print(info["player_0"]["t"], info["player_0"]["score"])
            traj_infos[id]["t"].append(info["player_0"]["t"])
            traj_infos[id]["score"].append(info["player_0"]["score"])
            total_score = sum(traj_infos[id]["score"])

            transition["outcome"] = outcome
            # add transition to buffer
            # last time step data will not be collected
            # check terminal condition
            {k for k, v in outcome.done.items() if v}

            # if done_agents == set(outcome.keys()):
            #     # self.env.graphic_pipeline.on_cleanup()
            #     status[id] = False
            #     break

            world = env._env.unwrapped.world
            current_event = world.get_current_event(world.agents)
            print(current_event)

            frame = env.render(mode=render_mode)
            data = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            params = [cv2.IMWRITE_PNG_COMPRESSION, 9]
            data = cv2.imencode(".png", data, params)[1]

            data = base64.b64encode(data.tobytes()).decode("utf8")
            if info["player_0"]["t"] % 10 == 0:
                info_list = update_info_list(
                    info_list, "agent", agent_infos[info["player_0"]["t"] % 6], info["player_0"]["t"]
                )
            if instructions[id] != 0:
                info_list = update_info_list(info_list, "human", INSTRUCTIONS[instructions[id]], info["player_0"]["t"])
                instructions[id] = 0
            if feedbacks[id] != 0:
                info_list = update_info_list(info_list, "human", FEEDBACK[feedbacks[id]], info["player_0"]["t"])
                feedbacks[id] = 0
            # if info["player_0"]["t"] % 5 == 0:
            #     info_list = update_info_list(
            #         info_list, "human", agent_infos[info["player_0"]["t"] % 6], info["player_0"]["t"]
            #     )
            state[id] = {
                "frame": data,
                "time": 1000 - info["player_0"]["t"],
                "score": total_score,
                "info_list": info_list,
            }
            # logger.info(f"{state[id]}")

            updated[id * 2] = True
            updated[id * 2 + 1] = True

            if 1000 - info["player_0"]["t"] == 0:
                filename = traj_names[id]
                with open(f"traj/{filename}.json", "w") as f:
                    content = json.dumps(traj_infos[id])
                    f.write(content)
                updated[id * 2] = False
                updated[id * 2 + 1] = False
                status[id] = False
                break

            await asyncio.sleep(60 / 400)
        # time.sleep(60/400)
        connection[id * 2] = False
        connection[id * 2 + 1] = False


# for i in range(MAX_GAME):
#     t = threading.Thread(target=startgame, args=(i, ))
#     t.start()


# for i in range(MAX_GAME):
# asyncio.run(startgame(i))
@app.before_serving
async def startup():
    loop = asyncio.get_event_loop()
    loop.create_task(startgames())


async def startgames():
    await asyncio.gather(*[startgame(i) for i in range(MAX_GAME)])


async def sending(id):
    print("start sending")
    while True:
        if status[id // 2] == False:
            break
        if updated[id]:
            await websocket.send(json.dumps(state[id // 2]))
            updated[id] = False
            if status[id // 2] == False:
                break
        await asyncio.sleep(0.01)
    print("end sending")


async def receiving(id):
    print("start receiving")
    global status, actions
    while status[id // 2]:
        recv = await websocket.receive()
        # print(action)
        action, instruction, feedback = recv.split(" ")
        if action != 0:
            actions[id] = int(action)
        if instruction != 0:
            instructions[id // 2] = int(instruction)
        if feedback != 0:
            feedbacks[id // 2] = int(feedback)
    print("end receiving")


@app.route("/beforegame", methods=["POST"])
def beforegame():
    if request.method == "POST":
        f = open("./config/before_game.yaml")
        config = yaml.load(f, Loader=yaml.FullLoader)

    return config


@app.route("/getsettings", methods=["POST"])
async def getsettings():
    global AGENT_ID, globalstate
    if request.method == "POST":
        # if globalstate == False:
        #     globalstate = True
        #     asyncio.run(startgames())
        #     return
        agent_id = AGENT_ID
        if AGENT_ID % 2 == 0:
            traj_names[AGENT_ID // 2] = time.time()
        traj_names[AGENT_ID // 2]
        AGENT_ID = (AGENT_ID + 1) % MAX_AGENT

        return jsonify(
            {"agentid": agent_id, "trajname": str(traj_names[AGENT_ID // 2]), "type": TYPE_TO_NAME[EXPERIMENT_TYPE]}
        )

        # return jsonify({"agentid": agent_id, "trajname": str(traj_name)})


@app.websocket(f"/<id>/connect")
async def handle_connect(id):
    print("WebSocket connected")

    id = int(id)
    status[id // 2] = True
    connection[id] = True
    producer = asyncio.create_task(sending(id))
    consumer = asyncio.create_task(receiving(id))
    # loop = asyncio.get_event_loop()
    # loop.create_task(asyncio.gather(producer, consumer))
    await asyncio.gather(producer, consumer)
    print("connect finish")


@app.websocket("/<id>/disconnect")
def handle_disconnect(id):
    print("WebSocket disconnected")


@app.websocket("/action")
def handle_action():
    pass


@app.route("/statement", methods=["POST"])
def statement():
    if request.method == "POST":
        f = open("./config/statement.md", encoding="utf-8").read()
        html = markdown(f)
    return html


@app.route("/create_questionnaire_before_game", methods=["POST"])
async def create_questionnaire_before_game():
    """
    {
        "name": "Bob",
        "sex": "male",
        "phone": "123456",
        "email":"abc@gmail.com",
        "age" : 20
    }
    Returns:

    """
    os.makedirs(questionnaire_savepath, exist_ok=True)
    request_data = await request.get_data()
    data_json = json.loads(request_data)
    questionnaire_path = os.path.join(questionnaire_savepath, f"{data_json.get('name')}_{data_json.get('phone')}")
    with open(f"{questionnaire_path}.json", "w") as f:
        f.write(json.dumps(data_json))
    return data_json


@app.route("/save_traj_info", methods=["POST"])
async def save_traj_info():
    request_data = await request.get_data()
    data_json = json.loads(request_data)
    print(data_json)
    os.path.join(questionnaire_savepath, f"{data_json.get('name')}_{data_json.get('phone')}")
    # with open(f"{questionnaire_path}.json") as f:
    #     questionnaire = json.load(f)

    # questionnaire["traj_name"] = data_json["traj_name"]
    # with open(f"{questionnaire_path}.json", "w") as fw:
    #     fw.write(json.dumps(questionnaire))
    # return {"a": "b"}


@app.route("/update_questionnaire_in_game", methods=["POST"])
async def create_questionnaire_in_game():
    """
    {
        "name": "Bob",
        "phone": "123456",
        "traj_id":"3_2_2023_9:30:44_human=0",
        "agent_type":"1",
        "questionnaire":{
            "I am playing well.": "I am playing well.",
            "The agent is playing poorly.": "The agent is playing poorly.",
            "The team is playing well.": "The team is playing well.",
    }
    Returns:

    """
    request_data = await request.get_data()
    data_json = json.loads(request_data)
    questionnaire_path = os.path.join(questionnaire_savepath, f"{data_json.get('name')}_{data_json.get('phone')}")
    with open(f"{questionnaire_path}.json") as f:
        questionnaire = json.load(f)
    if "in_game" not in questionnaire.keys():
        in_game = []
    else:
        in_game = questionnaire["in_game"]
    traj_id = data_json["traj_id"]
    save_path = os.path.normpath(traj_savepath)
    filename = f"{traj_id}.json".replace(":", "_")
    # agent_settings_list = list(data_json['agent_settings_list'])
    # agent_type_idx = int(data_json["agent_type"])
    # try:
    #     # agent, human = tuple(game_settings[int(data_json["agent_type"])]['agents'])
    #     agent, human = agent_settings_list[agent_type_idx]['agents']
    # except KeyError as e:
    #     print(e)
    #     agent, human = None, None

    # if human != "human":
    #     agent, human = human, agent
    #     human_pos = 0
    # else:
    #     human_pos = 1
    # agent_count = 0
    # for in_game_item in in_game:
    #     if in_game_item.get("teammate") == agent:
    #         agent_count += 1
    in_game.append(
        {
            "traj_path": os.path.normpath(os.path.join(save_path, filename)).replace("\\", "/"),
            "questionnaire": data_json["questionnaire"],
        }
    )
    questionnaire["in_game"] = in_game
    with open(f"{questionnaire_path}.json", "w") as fw:
        fw.write(json.dumps(questionnaire))
    return questionnaire


@app.route("/update_questionnaire_after_game", methods=["POST"])
async def create_questionnaire_after_game():
    """
    {
    "name": "Bob",
    "phone": "123456",
    "questionnaire": {
        "question1": "answer1",
        "question2": "answer2"
        }
    }

    Returns:

    """
    request_data = await request.get_data()
    data_json = json.loads(request_data)
    questionnaire_path = os.path.join(questionnaire_savepath, f"{data_json.get('name')}_{data_json.get('phone')}")
    with open(f"{questionnaire_path}.json") as f:
        questionnaire = json.load(f)
    after_game = data_json["questionnaire"]
    questionnaire["after_game"] = {"questionnaire": after_game}
    with open(f"{questionnaire_path}.json", "w") as fw:
        fw.write(json.dumps(questionnaire))
    return questionnaire


@app.route("/")
async def index():
    return await app.send_static_file("index.html")


@app.route("/html/<page>")
async def return_html(page):
    return await app.send_static_file(f"{page}.html")


@app.route("/inigame")
def inigame():
    [env.reset() for env in envs]


if __name__ == "__main__":
    # for i in range(MAX_GAME):
    #     t = threading.Thread(target=startgame, args=(i,))
    #     t.start()
    # loop = asyncio.get_event_loop()

    # loop.run_until_complete(asyncio.wait([startgames(), app.run(host='0.0.0.0', port=5001)]))
    # loop.close()
    app.run(host="0.0.0.0", port=5001)
    # asyncio.run(main())
    # asyncio.run(startgames())
