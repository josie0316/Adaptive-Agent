import asyncio
import base64
import io
import json
import os
import random
import sys
import time
from copy import deepcopy
from pprint import pformat

import yaml
from hypercorn.asyncio import serve
from hypercorn.config import Config
from loguru import logger
from markdown import markdown
from PIL import Image
from quart import Quart, jsonify, request, websocket

from agents.adaptive_dpt_agent import AdaptiveDPTAgent, AdaptiveDPTAgentNoFSM
from agents.comm_infer_llm_agent import CommInferAgent, CommInferAgentNoFSM
from agents.mid_agent import MidAgent
from agents.react_llm_agent import ReActAgent, ReActAgentNoFSM
from agents.reflexion_llm_agent import ReflexionAgent, ReflexionAgentNoFSM
from agents.text_agent import TextAgent
from coop_marl.controllers import MultiController
from coop_marl.envs.overcooked.overcooked_maker import OvercookedMaker

# from coop_marl.runners.runners import PlayRunner
from coop_marl.utils import Arrdict, create_parser, parse_args, utils
from llms.get_llm_output import get_openai_llm_output
from utils.history import History

GAME_ID = 0
MAX_GAME = 15
MAX_AGENT = MAX_GAME
MAX_PHASE = 8

STEP_INTERVAL = 0.25
# STEP_INTERVAL = 0.1  #! for debug
if STEP_INTERVAL != 0.25:
    logger.warning(f"STEP_INTERVAL is set to {STEP_INTERVAL}, which is only for debug!!!")

MAX_INFO_LENGTH = 10

PROGRESS_EVENT = asyncio.Event()
PROGRESS_LOCK = asyncio.Lock()
HUMAN_INPUT_LOCK = asyncio.Lock()

EXPERIMENT_TYPE = 0
TYPE_TO_NAME = {0: "HA", 1: "H", 2: "A", 3: "N"}

# PHASE_2_AGENT = {
#    -1: "warmup",
#    0: "trail",
#    1: "react",
#    2: "react",
#    3: "reflexion",
#    4: "reflexion",
#    5: "wtom",
#    6: "wtom",
#    7: "wotom",
#    8: "wotom",
#}

# 1. Register new agent for rounds 9, 10, 11, 12
PHASE_2_AGENT = {
    -1: "warmup",
    0: "trail",
    9: "adaptive_dpt",
    10: "adaptive_dpt",
    11: "adaptive_dpt",
    12: "adaptive_dpt",
}


if EXPERIMENT_TYPE == 0:
    SEND_MESSAGE = True
    RECEIVE_MESSAGE = True
elif EXPERIMENT_TYPE == 1:
    SEND_MESSAGE = False
    RECEIVE_MESSAGE = True
elif EXPERIMENT_TYPE == 2:
    SEND_MESSAGE = True
    RECEIVE_MESSAGE = False
elif EXPERIMENT_TYPE == 3:
    SEND_MESSAGE = False
    RECEIVE_MESSAGE = False


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

questionnaire_savepath = "./data/questionnaire"
traj_savepath = "./data/traj"
progress_savepath = "./data/progress.json"

app = Quart(__name__)


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


def process_frame(frame):
    image = Image.fromarray(frame)
    buffered = io.BytesIO()
    image.save(buffered, format="PNG", compress_level=9, optimize=True)
    base64_encoded = base64.b64encode(buffered.getvalue()).decode("utf8")

    # logger.info(f"png process_frame time: {e_time - s_time}, size: {len(base64_encoded)/1024:.2f}KB")
    return base64_encoded


async def run_inner_loop(id, outcome, current_traj_element, info_list):

    env = envs[id]
    controller = controllers[id]
    dummy_decision = controller.get_prev_decision_view()
    world = env._env.unwrapped.world
    episode_end = False
    if game_phases[id] >= 0:
        _max_steps = half_max_steps
    else:
        _max_steps = quarter_and_half_max_steps

    while True:
        # for each step
        while True:
            if connection[id] or not id_assigned[id]:
                break
            logger.trace(f"{id} not connect and assigned")
            await asyncio.sleep(1)
        if not id_assigned[id]:
            break
        logger.debug(f"{id}=")
        decision = Arrdict({p: dummy_decision[p] for p in outcome})
        inp = Arrdict(data=outcome, prev_decision=decision)
        current_action = [0, 0]
        action = 0
        if game_phases[id] > 0:
            logger.debug("NOT TRAIL")
            for i, k in enumerate(inp.data.keys()):
                if i == llm_idxs[id]:
                    if not mid_actions[id]:
                        current_traj_element["mid_action"] = None
                        json_state_simple = envs[id].get_json_state_simple(llm_idxs[id])
                        if PHASE_2_AGENT[game_phases[id]] == "reflexion":
                            to_reflections[id] = rule_agents[id].to_reflection(json_state_simple)
                        try:
                            action_result = rule_agents[id].get_action(json_state_simple)
                            logger.debug(f"Agent {type(rule_agents[id]).__name__} returned: {action_result} (type: {type(action_result)})")
                            mid_actions[id] = action_result
                        except Exception as e:
                            logger.error(e)
                            mid_actions[id] = None
                        else:
                            message_dict = {}
                            history_buffers[id].add(
                                current_steps[id],
                                json_state_simple,
                                message_dict,
                            )
                            logger.debug(
                                "History:\n"
                                + pformat([info._asdict() for info in history_buffers[id].get_history(1)])
                                + "\n" * 2
                            )
                    elif mid_actions[id]:
                        current_traj_element["mid_action"] = mid_actions[id]
                        try:
                            end, action, sta = mid_agents[id].get_action(mid_actions[id][0], **mid_actions[id][1])
                        except Exception as e:
                            logger.error(e)
                            end = True
                            action = 0
                            sta = "Failed"
                        else:
                            if end:
                                mid_actions[id] = None
                                if "Failed" in sta:
                                    logger.warning(sta)
                    current_action[i] = action
                else:
                    async with HUMAN_INPUT_LOCK:
                        current_action[i] = actions[id]
                        actions[id] = 0
        else:
            for i, k in enumerate(inp.data.keys()):
                if i == human_idxs[id]:
                    async with HUMAN_INPUT_LOCK:
                        current_action[i] = actions[id]
                        actions[id] = 0
                else:
                    current_action[i] = 0

        logger.debug(f"{current_action=}")
        decision = controller.select_actions(current_action, inp)
        current_traj_element["action"] = deepcopy(current_action)
        logger.debug(f"{decision=}")

        transition = Arrdict(inp=inp, decision=decision)

        # env step
        traj_infos[id]["traj"].append(current_traj_element)
        # Save state_before before env.step for order completion check
        state_before = envs[id].get_json_state_simple(llm_idxs[id])
        outcome, info = env.step(decision)
        # Save state_after after env.step for order completion check
        state_after = env.get_json_state_simple(llm_idxs[id])
        # Check for order completion by deliver_log or total_score
        deliver_log_before = state_before.get('deliver_log', [])
        deliver_log_after = state_after.get('deliver_log', [])
        total_score_before = state_before.get('total_score', 0.0)
        total_score_after = state_after.get('total_score', 0.0)
        # Only send 'good job' when the score increases (i.e., after a successful delivery)
        if total_score_after > last_total_score[id]:
            if rule_agents[id] is not None and rule_agents[id].mode == "ai_led" and rule_agents[id].send_message:
                logger.info("Order completed! Sending good job.")
                info_list = update_info_list(info_list, "agent", "good job", info["player_0"]["t"])
                current_traj_element["message"].append((llm_idxs[id], "good job"))
        last_total_score[id] = total_score_after
        logger.debug(f"""Timestep and score: {info["player_0"]["t"]}, {info["player_0"]["score"]}""")
        # total_score = sum(traj_infos[id]["score"])
        total_score = sum(ele["score"] for ele in traj_infos[id]["traj"])
        current_traj_element = {
            "t": info["player_0"]["t"],
            "score": info["player_0"]["score"],
            "state": str(env.get_json_state_simple(llm_idxs[id])),
            "message": [],
        }
        logger.debug(current_traj_element["state"])

        transition["outcome"] = outcome

        if game_phases[id] >= 0:
            try:
                text_actions = world.get_events()
            except Exception as e:
                logger.error(e)
                text_actions = {}
            for a_i, t_acts in text_actions.items():
                if len(t_acts) > len(agent_text_actions[id][a_i]):
                    logger.trace(f"Agent {a_i} perform text_action {t_acts[len(agent_text_actions[id][a_i]):]}")
                    agent_text_actions[id][a_i] = t_acts
                    traj_infos[id]["text_action"].append({"t": current_steps[id], "agent": a_i, "action": t_acts[-1]})
        if game_phases[id] > 0:
            try:
                current_mid_actions = world.get_mid_actions()
            except Exception as e:
                logger.error(e)
                current_mid_actions = {}

            for a_i, m_acts in current_mid_actions.items():
                if len(m_acts) > len(agent_mid_actions[id][a_i]):
                    # logger.debug(f"Agent {a_i} perform mid_action {m_acts[len(agent_mid_actions[id][a_i]):]}")
                    agent_mid_actions[id][a_i].append(m_acts[len(agent_mid_actions[id][a_i])])
                    history_buffers[id].add_action(agent_mid_actions[id][a_i][-1], a_i)

        frame = env.render(mode=render_mode)
        data = process_frame(frame)

        # After agent acts, set agent message in AI-led mode
        if game_phases[id] > 0:
            if rule_agents[id].mode == "ai_led" and rule_agents[id].send_message:
                json_state_simple = envs[id].get_json_state_simple(llm_idxs[id])
                assignment = rule_agents[id].get_message(json_state_simple)
                # Only send assignment if it's different from the last one sent
                if assignment and assignment != last_sent_assignment[id]:
                    logger.info(f"Send assignment: {assignment}")
                    info_list = update_info_list(info_list, "agent", assignment, info["player_0"]["t"])
                    current_traj_element["message"].append((llm_idxs[id], assignment))
                    last_sent_assignment[id] = assignment
        human_message = ""
        async with HUMAN_INPUT_LOCK:
            if instructions[id] != 0:
                if instructions[id] != 9:
                    human_message = f"We need {INSTRUCTIONS[instructions[id]]}"
                else:
                    human_message = "Fire!"

                # For phase -1 and 0, just log/display the human message, do not process with agent
                if game_phases[id] in [-1, 0]:
                    info_list = update_info_list(info_list, "human", human_message, info["player_0"]["t"])
                    instructions[id] = 0
                    feedbacks[id] = 0
                else:
                    # Route human instruction to agent if in human-led mode
                    if rule_agents[id].mode == "human_led":
                        rule_agents[id].receive_human_instruction(human_message)
                    info_list = update_info_list(info_list, "human", human_message, info["player_0"]["t"])
                    instructions[id] = 0

        async with HUMAN_INPUT_LOCK:
            if feedbacks[id] != 0:
                human_message = FEEDBACK[feedbacks[id]]
                # For phase -1 and 0, just log/display the human feedback, do not process with agent
                if game_phases[id] in [-1, 0]:
                    info_list = update_info_list(info_list, "human", human_message, info["player_0"]["t"])
                    feedbacks[id] = 0
                else:
                    info_list = update_info_list(info_list, "human", human_message, info["player_0"]["t"])
                    feedbacks[id] = 0
        if human_message and game_phases[id] > 0:
            history_buffers[id].add_message(human_message, 1 - llm_idxs[id])
            current_traj_element["message"].append((human_idxs[id], human_message))

        state[id] = {
            "frame": data,
            "time": _max_steps - info["player_0"]["t"],
            "score": total_score,
            "info_list": info_list,
            "agent_mode": rule_agents[id].mode if rule_agents[id] is not None else "unknown",
        }

        updated[id] = True
        current_steps[id] = env.timestep

        if game_phases[id] > 0:
            if len(rule_agents[id].text_assign_tasks) > 0:
                current_traj_element["assigned_tasks"] = rule_agents[id].text_assign_tasks

        if current_steps[id] > 0 and (current_steps[id] % urgent_response_interval_n_timestep == 0 or human_message):
            to_urgent_responses[id] = True
        if PHASE_2_AGENT[game_phases[id]] in ["wtom", "wotom"]:
            if current_steps[id] > 0 and current_steps[id] % reflection_interval_n_timestep == 0:
                to_reflections[id] = True

        if _max_steps - info["player_0"]["t"] == 0:
            if game_phases[id] >= 0:
                filename = f"{traj_names[id]}".replace(":", "_")
                traj_path = f"{traj_savepath}/{filename}.json".replace("\\", "/")
                with open(traj_path, "w") as f:
                    logger.info(f"save traj to {traj_path}")
                    json.dump(traj_infos[id], f, ensure_ascii=False)
            await asyncio.sleep(1)
            status[id] = False
            episode_end = True
            logger.info(f"Game finished at step {_max_steps} for {id_name_phone_list[id]} in phase {game_phases[id]}")
            break
        await asyncio.sleep(STEP_INTERVAL)

    return episode_end


async def startgame(id):

    global urgent_response_history_n_event, reflection_history_n_event
    try:
        logger.info(f"startgame {id}")
        env = envs[id]
        controller = controllers[id]
        controller.get_prev_decision_view()

        while True:
            # for each episode
            while not id_assigned[id]:
                logger.trace(f"game {id} wait for assignment")
                await asyncio.sleep(0.1)

            # Wait for connection
            while not connection[id]:
                logger.trace(f"game {id} for connection {id}")
                await asyncio.sleep(1)

            while game_phases[id] is None:
                await asyncio.sleep(1)

            traj_infos[id] = {
                "traj": [],  # time, state, action, score, message, mid_action
                "urgent_response": [],  # time, input, output, latency
                "reflection": [],  # time, input, output, latency
                "text_action": [],  # time, agent, action
            }

            await PROGRESS_EVENT.wait()
            PROGRESS_EVENT.clear()
            if game_phases[id] >= 0:
                _max_steps = half_max_steps
            else:
                _max_steps = quarter_and_half_max_steps

            outcome = env.reset(_max_steps)

            env._env.unwrapped.world.agents[1 - llm_idxs[id]].color = "black"
            if game_phases[id] <= 0:
                env._env.unwrapped.world.agents[llm_idxs[id]].color = "blue"
            elif PHASE_2_AGENT[game_phases[id]] == "react":
                env._env.unwrapped.world.agents[llm_idxs[id]].color = "red"
            elif PHASE_2_AGENT[game_phases[id]] == "reflexion":
                env._env.unwrapped.world.agents[llm_idxs[id]].color = "orange"
            elif PHASE_2_AGENT[game_phases[id]] == "wtom":
                env._env.unwrapped.world.agents[llm_idxs[id]].color = "pink"
            elif PHASE_2_AGENT[game_phases[id]] == "wotom":
                env._env.unwrapped.world.agents[llm_idxs[id]].color = "magenta"
            frame = env.render(mode=render_mode)
            data = process_frame(frame)

            # RESET
            info_list = []
            state[id] = {"frame": data, "time": _max_steps, "score": 0, "info_list": info_list}
            updated[id] = True
            current_traj_element = {
                "t": 0,
                "score": 0,
                "state": str(env.get_json_state_simple(llm_idxs[id])),
                "message": [],
                "assigned_tasks": [],
            }

            mid_actions[id] = None

            if game_phases[id] > 0:
                if PHASE_2_AGENT[game_phases[id]] == "wotom":
                    if FSM:
                        rule_agents[id] = CommInferAgent(
                            text_agents[id],
                            envs[id]._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            infer_human=False,
                        )
                    else:
                        rule_agents[id] = CommInferAgentNoFSM(
                            text_agents[id],
                            env._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            infer_human=False,
                        )
                elif PHASE_2_AGENT[game_phases[id]] == "wtom":
                    if FSM:
                        rule_agents[id] = CommInferAgent(
                            text_agents[id],
                            envs[id]._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            infer_human=True,
                        )
                    else:
                        rule_agents[id] = CommInferAgentNoFSM(
                            text_agents[id],
                            env._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            infer_human=True,
                        )
                elif PHASE_2_AGENT[game_phases[id]] == "adaptive_dpt":
                    # Set initial mode for each phase
                    if game_phases[id] in [9, 10, 12]:
                        initial_mode = "ai_led"
                    elif game_phases[id] == 11:
                        initial_mode = "human_led"
                    else:
                        initial_mode = "ai_led"
                    rule_agents[id] = AdaptiveDPTAgent(
                        text_agents[id],
                        envs[id]._env.unwrapped.world,
                        initial_mode=initial_mode,
                        send_message=SEND_MESSAGE,
                        receive_message=RECEIVE_MESSAGE,
                        infer_human=True,
                    )
                elif PHASE_2_AGENT[game_phases[id]] == "reflexion":
                    if FSM:
                        rule_agents[id] = ReflexionAgent(
                            text_agents[id],
                            envs[id]._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            max_n_react_turn=urgent_response_history_n_event,
                            max_n_reflection_event=reflection_history_n_event,
                        )
                    else:
                        rule_agents[id] = ReflexionAgentNoFSM(
                            text_agents[id],
                            env._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            max_n_react_turn=urgent_response_history_n_event,
                            max_n_reflection_event=reflection_history_n_event,
                        )
                elif PHASE_2_AGENT[game_phases[id]] == "react":
                    if FSM:
                        rule_agents[id] = ReActAgent(
                            text_agents[id],
                            envs[id]._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            max_n_react_turn=urgent_response_history_n_event,
                        )
                    else:
                        rule_agents[id] = ReActAgentNoFSM(
                            text_agents[id],
                            env._env.unwrapped.world,
                            send_message=SEND_MESSAGE,
                            receive_message=RECEIVE_MESSAGE,
                            max_n_react_turn=urgent_response_history_n_event,
                        )
                else:
                    logger.error(f"game_phases[id] {game_phases[id]} error!")

            logger.info(
                f"game phase {game_phases[id]} with steps {_max_steps} for {id_name_phone_list[id]} in game id {id}"
            )

            if game_phases[id] >= 0:
                world = env._env.unwrapped.world
                agent_text_actions[id] = {a_i: [] for a_i in range(env._env.num_agents)}
                agent_mid_actions[id] = {a_i: [] for a_i in range(env._env.num_agents)}

            if game_phases[id] > 0:
                text_agents[id].update_agent(world, llm_idxs[id])
                # MARK: world will change after reset
                mid_agents[id].update(text_agents[id], world)
                rule_agents[id].update(text_agents[id], world, envs[id].get_json_state_simple(llm_idxs[id]))
                history_buffers[id].reset(_max_steps)

            episode_end = False
            try:
                episode_end = await run_inner_loop(id, outcome, current_traj_element, info_list)
            except KeyboardInterrupt:
                logger.error("Ctrl+C detected")
                raise
            except:
                is_game_healthy[id] = False
            connection[id] = False
            rule_agents[id] = None
            if episode_end:
                if game_phases[id] != last_phases[id]:
                    pass
                else:
                    logger.info(f"All game finished for {id_name_phone_list[id]} in game_id {id}")
                    async with PROGRESS_LOCK:
                        with open(progress_savepath, encoding="utf-8") as f:
                            progress = json.load(f)
                        progress[id_name_phone_list[id]]["game_id"] = -1
                        with open(progress_savepath, "w", encoding="utf-8") as f:
                            json.dump(progress, f, ensure_ascii=False)
                    id_name_phone_list[id] = None
                    id_assigned[id] = False
    except KeyboardInterrupt:
        logger.error("Ctrl+C detected")
        raise
    except:
        is_game_healthy[id] = False


async def react(id) -> str:
    global current_steps, max_steps, MODEL
    while True:
        if to_urgent_responses[id] and id_assigned[id] and PHASE_2_AGENT[game_phases[id]] in ["react", "reflexion"]:
            try:
                ## get recent history of specified length
                history = history_buffers[id].get_formatted_history(1, llm_idxs[id])
                logger.debug("History:\n" + history)

                ## rule_agent is to be defined in "react_llm_agent.py"
                ## game prompt + goal prompt + output prompt (+ few-shot examples)
                rule_agents[id].update_trajectory(history)
                if PHASE_2_AGENT[game_phases[id]] == "react":
                    llm_input = rule_agents[id].get_react_llm_input()
                elif PHASE_2_AGENT[game_phases[id]] == "reflexion":
                    llm_input = rule_agents[id].get_reflection_react_llm_input()
                else:
                    raise ValueError(f"Agent {PHASE_2_AGENT[game_phases[id]]} not supported")
                logger.trace("ReAct LLM Input")
                logger.trace(llm_input[1]["content"])
                s_time = time.time()

                ## interact with an LLM, generate thought and action together
                llm_output = await get_openai_llm_output(MODEL, llm_input)
                e_time = time.time()
                traj_infos[id]["urgent_response"].append(
                    {"t": current_steps[id], "input": llm_input, "output": llm_output, "latency": e_time - s_time}
                )
                logger.success(f"ReAct LLM Output, Used {e_time - s_time: .4f}s")
                logger.trace("ReAct LLM Output")
                logger.trace(llm_output)

                thought_task = rule_agents[id].update_assigned_tasks(llm_output)
                if thought_task:
                    rule_agents[id].update_react(thought_task[0], thought_task[1])
                else:
                    rule_agents[id].update_react(llm_output, "")
                to_urgent_responses[id] = False
            except KeyboardInterrupt:
                logger.error("Ctrl+C")
                raise
            except Exception as e:
                logger.error(e)
                to_urgent_responses[id] = False

        # if current_steps >= max_steps:
        #     break
        await asyncio.sleep(0.1)


async def reflection(id) -> str:
    global reflection_history_n_event, reflection_interval_n_timestep
    global max_steps
    while True:
        # if env.timestep > 0 and env.timestep % reflection_interval_n_timestep == 0:
        if to_reflections[id] and id_assigned[id]:
            try:
                history = history_buffers[id].get_formatted_history(reflection_history_n_event, llm_idxs[id])
                logger.debug("History:\n" + history)

                if PHASE_2_AGENT[game_phases[id]] == "reflexion":
                    llm_input = rule_agents[id].get_reflection_llm_input()
                elif PHASE_2_AGENT[game_phases[id]] in ["wtom", "wotom"]:
                    llm_input = rule_agents[id].get_reflection_llm_input(history)
                else:
                    raise ValueError(f"Agent {PHASE_2_AGENT[game_phases[id]]} not supported")
                logger.debug("Reflection LLM Input")
                logger.debug(llm_input[1]["content"])
                s_time = time.time()
                llm_output = await get_openai_llm_output(MODEL, llm_input)
                e_time = time.time()
                traj_infos[id]["reflection"].append(
                    {"t": current_steps[id], "input": llm_input, "output": llm_output, "latency": e_time - s_time}
                )
                logger.info(f"Game {id} Reflection LLM Output, Used {e_time - s_time: .4f}s")
                logger.debug(llm_output)
                # if rule_agents[id].dummy_json_state:  # agent is ready
                rule_agents[id].update_reflection(llm_output)
                to_reflections[id] = False
            except KeyboardInterrupt:
                logger.error("Ctrl+C")
                raise
            except Exception as e:
                logger.error(e)
                to_reflections[id] = False
        # if current_steps[id] >= max_steps:
        #     break
        await asyncio.sleep(1)


async def urgent_response(id) -> str:
    global urgent_response_history_n_event, urgent_response_interval_n_timestep
    global max_steps

    while True:
        if to_urgent_responses[id] and id_assigned[id] and PHASE_2_AGENT[game_phases[id]] in ["wtom", "wotom"]:
            try:
                history = history_buffers[id].get_formatted_history(urgent_response_history_n_event, llm_idxs[id])
                logger.debug("History:\n" + history)
                llm_input = rule_agents[id].get_urgent_response_llm_input(history)
                logger.debug("Urgent Response LLM Input")
                logger.debug(llm_input[1]["content"])
                s_time = time.time()
                llm_output = await get_openai_llm_output(MODEL, llm_input)
                e_time = time.time()
                traj_infos[id]["urgent_response"].append(
                    {"t": current_steps[id], "input": llm_input, "output": llm_output, "latency": e_time - s_time}
                )
                logger.info(f"Game {id} Urgent Response LLM Output, Used {e_time - s_time: .4f}s")
                logger.debug(f"Output:\n{llm_output}")
                # if rule_agents[id].dummy_json_state:  # agent is ready
                rule_agents[id].update_assigned_tasks(llm_output)
                if rule_agents[id].message:
                    history_buffers[id].add_message(rule_agents[id].message, llm_idxs[id])
                traj_infos[id]["urgent_response"].append(
                    {"t": current_steps[id], "input": llm_input, "output": llm_output}
                )
                to_urgent_responses[id] = False
            except KeyboardInterrupt:
                logger.error("Ctrl+C")
                raise
            except Exception as e:
                logger.error(e)
                to_urgent_responses[id] = False
        # if current_steps[id] >= max_steps:
        #     break
        await asyncio.sleep(0.1)


@app.before_serving
async def startup():
    loop = asyncio.get_event_loop()
    loop.create_task(start_games())
    loop.create_task(start_reflections())
    loop.create_task(start_reacts())
    loop.create_task(start_urgent_responses())
    loop.create_task(start_check_connections())


async def start_check_connections():
    await asyncio.gather(*[check_connection(i) for i in range(MAX_GAME)])


async def start_games():
    await asyncio.gather(*[startgame(i) for i in range(MAX_GAME)])


async def start_reflections():
    await asyncio.gather(*[reflection(i) for i in range(MAX_GAME)])


async def start_reacts():
    await asyncio.gather(*[react(i) for i in range(MAX_GAME)])


async def start_urgent_responses():
    await asyncio.gather(*[urgent_response(i) for i in range(MAX_GAME)])


async def sending(id):
    logger.trace("start sending")
    while True:
        if status[id] == False:
            updated[id] = False
            break
        if updated[id]:
            await websocket.send(json.dumps(state[id]))
            updated[id] = False
            if status[id] == False:
                break
        await asyncio.sleep(STEP_INTERVAL / 10)
    logger.trace("end sending")


async def receiving(id):
    logger.trace("start receiving")
    global status, actions
    while status[id]:
        recv = await websocket.receive()
        # logger.trace(action)
        async with HUMAN_INPUT_LOCK:
            # Check if this is a mode switch message
            if recv.startswith("MODE_SWITCH:"):
                mode = recv.split(":")[1].strip()
                if mode in ["ai_led", "human_led"] and rule_agents[id] is not None:
                    success = rule_agents[id].switch_mode(mode)
                    if success:
                        logger.info(f"Game {id}: Mode switched to {mode}")
                        # Update experiment type based on mode
                        if mode == "ai_led":
                            # AI-led mode: agent sends messages, human receives
                            rule_agents[id].send_message = True
                            rule_agents[id].receive_message = False
                        else:  # human_led
                            # Human-led mode: human sends messages, agent receives
                            rule_agents[id].send_message = False
                            rule_agents[id].receive_message = True
                    else:
                        logger.warning(f"Game {id}: Failed to switch mode to {mode}")
            else:
                # Regular action/instruction/feedback message
                action, instruction, feedback = recv.split(" ")
                if action != 0:
                    actions[id] = int(action)
                if instruction != 0:
                    instructions[id] = int(instruction)
                if feedback != 0:
                    feedbacks[id] = int(feedback)
        connection[id] = True
    logger.trace("end receiving")


@app.route("/beforegame", methods=["POST"])
def beforegame():
    if request.method == "POST":
        f = open("./config/before_game.yaml", encoding="utf-8")
        config = yaml.load(f, Loader=yaml.FullLoader)

    return config


@app.route("/getsettings", methods=["POST"])
async def getsettings():
    global GAME_ID, globalstate, MAX_GAME
    # logger.success(f"{GAME_ID=}")

    if request.method == "POST":
        # if globalstate == False:
        #     globalstate = True
        #     asyncio.run(startgames())
        #     return
        async with PROGRESS_LOCK:
            request_data = await request.get_data()
            data_json = json.loads(request_data)
            id_name_phone = f"""{data_json["name"]}_{data_json["phone"]}"""
            with open(progress_savepath, encoding="utf-8") as f:
                progress = json.load(f)

            if id_name_phone in progress.keys():
                # Existing user, check id
                # logger.info(f"restore for {id_name_phone}")
                if progress[id_name_phone]["game_id"] != -1:
                    # still connected, the memory can be used
                    agent_id = progress[id_name_phone]["game_id"]
                else:
                    # reconnected
                    available_id = -1
                    while available_id == -1:
                        for i in range(MAX_GAME):
                            if not id_assigned[i] and is_game_healthy[i]:
                                available_id = i
                                break
                        if available_id == -1:
                            logger.warning(f"No available id for {id_name_phone}")
                            await asyncio.sleep(5)
                    agent_id = available_id

                id_name_phone_list[agent_id] = id_name_phone
                user_config = progress[id_name_phone]["config"]

                if user_config["RECEIVE_MESSAGE"] != RECEIVE_MESSAGE or user_config["SEND_MESSAGE"] != SEND_MESSAGE:
                    logger.warning(
                        f"{id_name_phone} is playing wrong config! user_config: {user_config}, current config: {RECEIVE_MESSAGE=} {SEND_MESSAGE=}"
                    )

                game_sequence[agent_id] = progress[id_name_phone]["game_sequence"]
                phase_idx = progress[id_name_phone]["game_sequence_idx"]
                if phase_idx < len(game_sequence[agent_id]):
                    if phase_idx >= 0:
                        game_phases[agent_id] = game_sequence[agent_id][phase_idx]
                    else:
                        game_phases[agent_id] = -1
                    last_phases[agent_id] = game_sequence[agent_id][-1]
                    game_sequence[agent_id] = iter(game_sequence[agent_id][phase_idx + 1 :])
                else:
                    game_phases[agent_id] = None
                    logger.error(f"A user {id_name_phone} has finished all phases but logged in again")

                traj_names[agent_id] = f"{id_name_phone}_{game_phases[agent_id]}_{time.time()}"
                progress[id_name_phone]["game_id"] = agent_id
                logger.info(f"restore for {id_name_phone} and id {agent_id}, phase {game_phases[agent_id]}")
            else:
                # New user
                available_id = -1
                while available_id == -1:
                    for i in range(MAX_GAME):
                        if not id_assigned[i] and is_game_healthy[i]:
                            available_id = i
                            break
                    if available_id == -1:
                        logger.warning(f"No available id for {id_name_phone}")
                        await asyncio.sleep(5)
                logger.info(f"new game settings for {id_name_phone} and id {available_id}")
                agent_id = available_id
                id_name_phone_list[agent_id] = id_name_phone

                game_phases[agent_id] = -1
                tmp_seq = [0, 9, 10, 11, 12]
                game_sequence[agent_id] = iter(tmp_seq)
                last_phases[agent_id] = tmp_seq[-1]

                traj_names[agent_id] = f"{id_name_phone}_{game_phases[agent_id]}_{time.time()}"
                progress[id_name_phone] = {
                    "game_sequence": list(tmp_seq),
                    "game_sequence_idx": -1,
                    "config": {"RECEIVE_MESSAGE": RECEIVE_MESSAGE, "SEND_MESSAGE": SEND_MESSAGE},
                    "game_id": agent_id,
                }

                logger.info(f"\n\n\n save progress {id_name_phone}\n\n\n")

            with open(progress_savepath, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False)

        id_assigned[agent_id] = True

        PROGRESS_EVENT.set()
        if game_phases[agent_id] is not None:
            if game_phases[agent_id] >= 0:
                _max_steps = half_max_steps
            else:
                _max_steps = quarter_and_half_max_steps
        else:
            _max_steps = 0
        ret = jsonify(
            {
                "agentid": agent_id,
                "trajname": str(traj_names[agent_id]),
                "type": TYPE_TO_NAME[EXPERIMENT_TYPE],
                "game_sequence_idx": progress[id_name_phone]["game_sequence_idx"],
                "max_steps": _max_steps,
            }
        )

        return ret


@app.route("/<id>/getphase", methods=["POST"])
async def getphase(id):
    if request.method == "POST":
        id = int(id)
        async with PROGRESS_LOCK:
            game_phase = game_phases[id]
            last_phase = last_phases[id]
            to_questionnaire = False
            request_data = await request.get_data()
            data_json = json.loads(request_data)
            id_name_phone = f"""{data_json["name"]}_{data_json["phone"]}"""
            questionnaire_path = os.path.join(questionnaire_savepath, f"{id_name_phone}.json")
            phase_key = f"phase_{game_phase}"
            if os.path.exists(questionnaire_path):
                with open(questionnaire_path, encoding="utf-8") as f:
                    questionnaire = json.load(f)
                if "in_game" in questionnaire.keys():
                    in_game = questionnaire["in_game"]
                    if phase_key in in_game.keys() and "traj_path" in in_game[phase_key].keys() and game_phase in [9, 11]:
                        logger.info(f"{game_phase}")
                        to_questionnaire = True
            with open(progress_savepath, encoding="utf-8") as f:
                progress = json.load(f)
        logger.info(progress)
        if progress.get(id_name_phone, None) is not None:
            game_seq = progress[id_name_phone]["game_sequence"]
            seq_idx = progress[id_name_phone]["game_sequence_idx"]
        else:
            game_seq = None
        if game_seq is not None:
            logger.info(game_seq)
            game_seq = game_seq[1 : seq_idx + 1]
            # logger.info(list(game_seq))
            return jsonify(
                {
                    "gamephase": game_phase,
                    "lastphase": last_phase,
                    "maxphase": MAX_PHASE,
                    "game_sequence": game_seq,
                    "to_questionnaire": to_questionnaire,
                }
            )
        else:
            logger.info("game_seq is None")
            return jsonify(
                {
                    "gamephase": game_phase,
                    "lastphase": last_phase,
                    "maxphase": MAX_PHASE,
                    "game_sequence": None,
                    "to_questionnaire": to_questionnaire,
                }
            )


@app.websocket(f"/<id>/connect")
async def handle_connect(id):

    id = int(id)
    status[id] = True
    connection[id] = True
    producer = asyncio.create_task(sending(id))
    consumer = asyncio.create_task(receiving(id))

    # logger.info(f"WebSocket {id} connected {connection[id]=} {status[id]=}")
    logger.info(f"WebSocket {id} connected")
    try:
        await asyncio.gather(producer, consumer)
    except asyncio.CancelledError:
        logger.info(f"Tasks cancelled for WebSocket {id}")
    except Exception as e:
        logger.error(f"Unexpected error for WebSocket {id}: {e}")
    finally:
        status[id] = False
        connection[id] = False
        logger.info(f"WebSocket {id} disconnected")


@app.route("/statement", methods=["POST"])
def statement():
    if request.method == "POST":
        with open("./config/statement.md", encoding="utf-8") as f:
            html = markdown(f.read())
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
    request_data = await request.get_data()
    data_json = json.loads(request_data) | {"exp_type": TYPE_TO_NAME[EXPERIMENT_TYPE]}
    questionnaire_path = os.path.join(questionnaire_savepath, f"{data_json.get('name')}_{data_json.get('phone')}")
    if os.path.exists(f"{questionnaire_path}.json"):
        with open(f"{questionnaire_path}.json", encoding="utf-8") as f:
            prev_data_json = json.load(f)
        data_json = prev_data_json | data_json
    with open(f"{questionnaire_path}.json", "w", encoding="utf-8") as f:
        json.dump(data_json, f, ensure_ascii=False)
    return data_json


@app.route("/save_traj_info", methods=["POST"])
async def save_traj_info():
    if request.method == "POST":
        request_data = await request.get_data()
        data_json = json.loads(request_data)
        async with PROGRESS_LOCK:
            with open(progress_savepath, encoding="utf-8") as f:
                progress = json.load(f)
            id_name_phone = f"{data_json.get('name')}_{data_json.get('phone')}"
            phase_idx = progress[id_name_phone]["game_sequence_idx"]
            # 移除自增操作，避免重复加一
            # if phase_idx <= 0 or phase_idx % 2 != 0:
            #     progress[id_name_phone]["game_sequence_idx"] += 1
            with open(progress_savepath, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False)
        if phase_idx >= 0:
            questionnaire_path = os.path.join(questionnaire_savepath, id_name_phone)
            with open(f"{questionnaire_path}.json", encoding="utf-8") as f:
                questionnaire = json.load(f)
            if "in_game" not in questionnaire.keys():
                in_game = {}
            else:
                in_game = questionnaire["in_game"]
            traj_id = data_json["traj_id"]
            save_path = os.path.normpath(traj_savepath)
            filename = f"{traj_id}.json".replace(":", "_")
            phase = int(data_json["gamephase"])
            phase_key = f"phase_{phase}"
            if phase_key in in_game.keys():
                logger.error(f"Phase {phase} in in_game")
            in_game[phase_key] = {
                "traj_path": os.path.normpath(os.path.join(save_path, filename)).replace("\\", "/"),
                "datetime": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
            }
            questionnaire["in_game"] = in_game
            with open(f"{questionnaire_path}.json", "w", encoding="utf-8") as fw:
                json.dump(questionnaire, fw, ensure_ascii=False)
        return jsonify({"status": "Success"})


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
    if not os.path.exists(f"{questionnaire_path}.json"):
        with open(f"{questionnaire_path}.json", "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(f"{questionnaire_path}.json", encoding="utf-8") as f:
        questionnaire = json.load(f)
    if "in_game" not in questionnaire.keys():
        in_game = {}
    else:
        in_game = questionnaire["in_game"]
    phase = int(data_json["gamephase"])
    phase_key = f"phase_{phase}"
    if phase_key not in in_game:
        in_game[phase_key] = {}

    # 新增：如果有 cognitive_load 字段，直接写入
    if "cognitive_load" in data_json:
        in_game[phase_key]["cognitive_load"] = data_json["cognitive_load"]

    # 下面是原有的问卷处理逻辑
    if "questionnaire" in data_json:
        order = data_json["questionnaire"]
        order_keys = list(order.keys())
        explicit_order = {key: {} for key in order_keys}
        key_to_name = {
            "0": "react",
            "1": "reflexion",
            "2": "wtom",
            "3": "wotom",
            "4": "adaptive_dpt",
        }
        print(order)
        print(explicit_order)
        for order_key in order_keys:
            for key in order[order_key]:
                if key in key_to_name:
                    explicit_order[order_key][key_to_name[key]] = order[order_key][key]
            else:
                logger.warning(f"Key {key} not in key_to_name mapping, skipping.")
        in_game[phase_key]["questionnaire"] = explicit_order

    questionnaire["in_game"] = in_game
    with open(f"{questionnaire_path}.json", "w", encoding="utf-8") as fw:
        json.dump(questionnaire, fw, ensure_ascii=False)
    async with PROGRESS_LOCK:
        with open(progress_savepath, encoding="utf-8") as f:
            progress = json.load(f)
        id_name_phone = f"{data_json.get('name')}_{data_json.get('phone')}"
        progress[id_name_phone]["game_sequence_idx"] += 1
        with open(progress_savepath, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False)
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
    with open(f"{questionnaire_path}.json", encoding="utf-8") as f:
        questionnaire = json.load(f)
    after_game = data_json["questionnaire"]
    questionnaire["after_game"] = {"questionnaire": after_game}
    with open(f"{questionnaire_path}.json", "w", encoding="utf-8") as fw:
        json.dump(questionnaire, fw, ensure_ascii=False)
    return questionnaire


@app.route("/log_fake_button_press", methods=["POST"])
async def log_fake_button_press():
    data = await request.get_json()
    # You can save to a file, database, or just log it
    log_path = "logs/fake_button_presses.jsonl"
    import os
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        import json
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
    print(f"Fake button press logged: {data}")
    return jsonify({"status": "ok"})


@app.route("/")
async def index():
    return await app.send_static_file("index.html")
    # return await app.send_static_file("index_aa.html")


@app.route("/html/<page>")
async def return_html(page):
    return await app.send_static_file(f"{page}.html")


@app.route("/inigame")
def inigame():
    [env.reset() for env in envs]


async def check_connection(id) -> str:
    while True:
        if id_assigned[id] and is_game_healthy[id]:
            if connection[id]:
                lost_time[id] = 0
            else:
                lost_time[id] += 1

        if lost_time[id] >= 300:
            logger.info(f"Connection lost for {id_name_phone_list[id]} in game_id {id}")
            async with PROGRESS_LOCK:
                with open(progress_savepath, encoding="utf-8") as f:
                    progress = json.load(f)
                progress[id_name_phone_list[id]]["game_id"] = -1
                with open(progress_savepath, "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False)
            id_name_phone_list[id] = None
            id_assigned[id] = False
            lost_time[id] = 0
        await asyncio.sleep(1)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    os.makedirs("logs", exist_ok=True)
    logger.add("logs/day4.log", level="TRACE")
    logger.add("logs/day4_less.log", level="INFO")
    args, conf, env_conf, _ = parse_args(create_parser())

    utils.set_random_seed(args.seed)

    logger.success("args\n" + pformat(args))
    logger.success("conf\n" + pformat(conf))
    logger.success("env_conf\n" + pformat(env_conf))

    reflection_history_n_event = conf.get("reflection_history_n_event", 10)
    reflection_interval_n_timestep = conf.get("reflection_interval_n_timestep", 50)
    urgent_response_history_n_event = conf.get("urgent_response_history_n_event", 3)
    urgent_response_interval_n_timestep = conf.get("urgent_response_interval_n_timestep", 20)
    max_steps = env_conf.get("horizon", 1000)

    half_max_steps = max_steps // 2
    quarter_and_half_max_steps = max_steps // 2 + max_steps // 4
    # quarter_and_half_max_steps = 1
    if quarter_and_half_max_steps != max_steps // 2 + max_steps // 4:
        logger.warning(f"quarter_and_half_max_steps is not {max_steps // 2 + max_steps // 4}!!!")

    MODEL = args.model
    FSM = args.fsm

    reg_env_name = env_conf.name
    del env_conf["name"]
    envs = [OvercookedMaker(**env_conf, display=True) for _ in range(MAX_GAME)]
    [env.reset() for env in envs]

    action_spaces = envs[0].action_spaces
    controllers = [MultiController(action_spaces) for _ in range(MAX_GAME)]

    num_episodes = 1
    render_mode = "rgb_array"

    status = [True for _ in range(MAX_GAME)]
    actions = [0 for _ in range(MAX_GAME)]
    instructions = [0 for _ in range(MAX_GAME)]
    feedbacks = [0 for _ in range(MAX_GAME)]
    connection = [False for _ in range(MAX_GAME)]
    to_reflections = [False for _ in range(MAX_GAME)]
    to_urgent_responses = [False for _ in range(MAX_GAME)]
    refresh = False

    state = [None for _ in range(MAX_GAME)]
    updated = [False for _ in range(MAX_GAME)]
    traj_infos = [None for _ in range(MAX_GAME)]

    globalstate = False

    traj_names = ["" for _ in range(MAX_GAME)]
    llm_idxs = [1 for _ in range(MAX_GAME)]
    human_idxs = [0 for _ in range(MAX_GAME)]
    current_steps = [0 for _ in range(MAX_GAME)]
    mid_actions = [None for _ in range(MAX_GAME)]
    id_assigned = [False for _ in range(MAX_GAME)]
    is_game_healthy = [True for _ in range(MAX_GAME)]
    lost_time = [0 for _ in range(MAX_GAME)]
    id_name_phone_list = [None for _ in range(MAX_GAME)]

    agent_text_actions = [{a_i: [] for a_i in range(env._env.num_agents)} for env in envs]
    agent_mid_actions = [{a_i: [] for a_i in range(env._env.num_agents)} for env in envs]

    #! remember to change back to 0
    game_phases = [-1 for _ in range(MAX_GAME)]  # 0 is trail

    text_agents = [TextAgent(envs[idx]._env.unwrapped.world, llm_idxs[idx]) for idx in range(MAX_GAME)]

    mid_agents = [MidAgent(text_agents[idx], envs[idx]._env.unwrapped.world) for idx in range(MAX_GAME)]
    rule_agents = [None] * MAX_GAME
    game_sequence = [None for _ in range(MAX_GAME)]
    last_phases = [0 for _ in range(MAX_GAME)]
    history_buffers = [History(max_steps=max_steps) for _ in range(MAX_GAME)]

    last_agent_message = [None for _ in range(MAX_GAME)]
    last_sent_assignment = [None for _ in range(MAX_GAME)]

    # Add these global variables near other per-id lists
    last_delivered_count = [0 for _ in range(MAX_GAME)]
    last_total_score = [0.0 for _ in range(MAX_GAME)]

    if not os.path.exists(progress_savepath):
        os.makedirs(os.path.dirname(progress_savepath), exist_ok=True)
        with open(progress_savepath, "w", encoding="utf-8") as f:
            json.dump({}, f)
            # user_progress:
            #     {
            #         user_id:
            #             - game_sequence
            #             - game_sequence_idx
            #             - config
            #     }
    else:
        with open(progress_savepath, encoding="utf-8") as f:
            progress = json.load(f)
        for user_id, user_progress in progress.items():
            user_progress["game_id"] = -1
        with open(progress_savepath, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False)
    os.makedirs(questionnaire_savepath, exist_ok=True)
    os.makedirs(traj_savepath, exist_ok=True)

    logger.success("Server started")
    config = Config()
    config.worker_class = "asyncio.ThreadPoolWorker"
    config.threads = 5
    config.bind = ["0.0.0.0:63000"]
    asyncio.run(serve(app, config))
