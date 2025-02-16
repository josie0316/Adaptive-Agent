import asyncio
import os
import sys
import time
from copy import deepcopy
from pprint import pformat

import pygame
from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.mid_agent import MidAgent
from agents.reflexion_llm_agent import ReflexionAgentNoFSM
from agents.text_agent import TextAgent
from coop_marl.controllers import LLMController
from coop_marl.envs.overcooked.overcooked_maker import OvercookedMaker
from coop_marl.utils import Arrdict, create_parser, parse_args, utils
from llms.get_llm_output import get_openai_llm_output
from utils.history import History

KeyToTuple_right = {
    pygame.K_RETURN: 5,
    pygame.K_UP: 4,
    pygame.K_DOWN: 3,
    pygame.K_RIGHT: 2,
    pygame.K_LEFT: 1,
}

key_to_message = {
    pygame.K_1: "LettuceBurger",
    pygame.K_KP1: "LettuceBurger",
    pygame.K_2: "BeefBurger",
    pygame.K_KP2: "BeefBurger",
    pygame.K_3: "BeefLettuceBurger",
    pygame.K_KP3: "BeefLettuceBurger",
    pygame.K_4: "Lettuce",
    pygame.K_KP4: "Lettuce",
    pygame.K_5: "Beef",
    pygame.K_KP5: "Beef",
    pygame.K_6: "Bread",
    pygame.K_KP6: "Bread",
    pygame.K_7: "Plate",
    pygame.K_KP7: "Plate",
    pygame.K_8: "Serve",
    pygame.K_KP8: "Serve",
    pygame.K_9: "Fire",
    pygame.K_KP9: "Fire",
    pygame.K_EQUALS: "Good Job!",
    pygame.K_KP_EQUALS: "Good Job!",
    pygame.K_MINUS: "Needs Improvement",
    pygame.K_KP_MINUS: "Needs Improvement",
}


## listens human action
async def listen_action():
    global current_action_right
    global human_message
    global current_steps, max_steps
    while True:
        event = pygame.event.get()
        if len(event) > 0:
            for e in event:

                ## when some key is pressed, KEYDOWN event is triggered
                if e.type == pygame.KEYDOWN:
                    current_action_right = 0

                    ## a valid action by human
                    if e.key in KeyToTuple_right:
                        current_action_right = KeyToTuple_right[e.key]

                    ## a message by human to AI
                    elif e.key in key_to_message:
                        if e.key in [
                            pygame.K_EQUALS,
                            pygame.K_KP_EQUALS,
                            pygame.K_MINUS,
                            pygame.K_KP_MINUS,
                            pygame.K_9,
                            pygame.K_KP9,
                        ]:
                            human_message = key_to_message[e.key]
                        else:
                            human_message = f"We need {key_to_message[e.key]}"

                ## quit the game
                elif e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

        if current_steps >= max_steps:
            break

        await asyncio.sleep(0.001)


### ReAct
async def react() -> str:
    global rule_agent, env, llm_idx
    global history_buffer
    # global urgent_response_history_n_event
    global current_steps, max_steps
    global to_react
    global MODEL
    global traj_infos

    while True:
        if to_react:  ## react with fixed time interval or in case of urgency
            # print("start reacting! ")
            ## get recent history of specified length
            history = history_buffer.get_formatted_history(1, llm_idx)
            logger.debug("History:\n" + history)

            ## rule_agent is to be defined in "react_llm_agent.py"
            ## game prompt + goal prompt + output prompt (+ few-shot examples)
            rule_agent.update_trajectory(history)
            llm_input = rule_agent.get_reflection_react_llm_input()
            logger.info("ReAct LLM Input")
            logger.info(llm_input[1]["content"])
            s_time = time.time()

            ## interact with an LLM, generate thought and action together
            # llm_output = await rule_agent.get_openai_llm_output(llm_input)
            llm_output = await get_openai_llm_output(MODEL, llm_input)
            e_time = time.time()
            logger.success(f"ReAct LLM Output, Used {e_time - s_time: .4f}s")
            logger.warning(f"Output:\n {llm_output}")

            traj_infos["urgent_response"].append(
                {"t": current_steps, "input": llm_input, "output": llm_output, "latency": e_time - s_time}
            )

            thought_task = rule_agent.update_assigned_tasks(llm_output)
            if thought_task:
                rule_agent.update_react(thought_task[0], thought_task[1])
            else:
                rule_agent.update_react(llm_output, "")
            to_react = False

        if current_steps >= max_steps:
            break
        await asyncio.sleep(0.1)


async def reflection() -> str:
    global rule_agent, env, llm_idx
    global history_buffer
    global reflection_history_n_event, reflection_interval_n_timestep
    global current_steps, max_steps
    global to_reflection
    global MODEL
    global traj_infos

    while True:
        if to_reflection:
            history = history_buffer.get_formatted_history(reflection_history_n_event, llm_idx)
            logger.debug("History:\n" + history)
            llm_input = rule_agent.get_reflection_llm_input()
            logger.info("Reflection LLM Input")
            logger.info(llm_input[1]["content"])
            s_time = time.time()
            # llm_output = await rule_agent.get_openai_llm_output(llm_input)
            llm_output = await get_openai_llm_output(MODEL, llm_input)
            e_time = time.time()
            traj_infos["reflection"].append(
                {"t": current_steps, "input": llm_input, "output": llm_output, "latency": e_time - s_time}
            )
            logger.success(f"Reflection LLM Output, Used {e_time - s_time: .4f}s")
            logger.warning(f"Reflection: {llm_output}")
            rule_agent.update_reflection(llm_output)
            to_reflection = False
        if current_steps >= max_steps:
            break
        await asyncio.sleep(1)


async def run_game():
    global current_action_right, human_message
    global text_agent, mid_agent, rule_agent
    global env
    global history_buffer
    global reflection_history_n_event, reflection_interval_n_timestep
    global max_steps, current_steps
    global to_react
    global to_reflection

    ## reset the env
    outcome = env.reset()
    env.render(mode=True)
    dummy_decision = controller.get_prev_decision_view()  ##??

    text_agent.update_agent(env._env.unwrapped.world, llm_idx)
    # MARK: world will change after reset
    mid_agent.update(text_agent, env._env.unwrapped.world)
    rule_agent.update(text_agent, env._env.unwrapped.world, env.get_json_state_simple(llm_idx))

    world: CookingWorld = env._env.unwrapped.world
    agent_text_actions = {a_i: [] for a_i in range(env._env.num_agents)}
    agent_mid_actions = {a_i: [] for a_i in range(env._env.num_agents)}

    json_state = world.get_json_state(llm_idx)
    logger.trace("state\n" + pformat(json_state))
    valid_actions = text_agent.get_valid_actions()
    logger.trace("valid text actions\n" + pformat(sorted(valid_actions)))

    mid_action = None
    action = 0
    current_action = [0, 0]
    episode_s_time = time.time()
    # init_mid_action = False

    current_traj_element = {
        "t": 0,
        "state": str(env.get_json_state_simple(llm_idx)),
        "score": 0,
        "message": [],
        "mid_action": None,
        "controlled_by_fsm": None,
    }
    # init_mid_action = False
    while True:
        decision = Arrdict({p: dummy_decision[p] for p in outcome})  ##??
        inp = Arrdict(data=outcome, prev_decision=decision)

        decision = Arrdict()

        for i, k in enumerate(inp.data.keys()):
            if i == llm_idx:
                if not mid_action:
                    current_traj_element["mid_action"] = None
                    json_state_simple = env.get_json_state_simple(llm_idx)
                    to_reflection = rule_agent.to_reflection(json_state_simple)

                    mid_action = rule_agent.get_action(json_state_simple)
                    if mid_action:
                        logger.warning(f"Reflexion Agent: {mid_action}")
                    message_dict = {}
                    ## mid action of LLM is saved here
                    # history_buffer.add(current_steps, json_state_simple, message_dict, {llm_idx: mid_action})
                    # init_mid_action = True
                    history_buffer.add(current_steps, json_state_simple, message_dict)
                    logger.debug(
                        "History:\n" + pformat([info._asdict() for info in history_buffer.get_history(1)]) + "\n" * 2
                    )
                if mid_action:
                    current_traj_element["mid_action"] = mid_action
                    end, action, status = mid_agent.get_action(mid_action[0], **mid_action[1])
                    # if init_mid_action and not end:
                    #     init_mid_action = False
                    #     history_buffer.add_action(mid_action, llm_idx)
                    if end:
                        ## when the task at hand is finished
                        mid_action = None
                        if "Failed" in status:
                            logger.success(status)
                        else:
                            logger.debug(status)
                current_traj_element["controlled_by_fsm"] = rule_agent.controlled_by_fsm
                current_action[i] = action
                decision[k] = Arrdict(action=action)
            ## this is an action listened from human key presses
            else:
                current_action[i] = current_action_right
                decision[k] = Arrdict(action=current_action_right)
        # env step
        current_traj_element["action"] = deepcopy(current_action)

        traj_infos["traj"].append(current_traj_element)
        outcome, info = env.step(decision)
        env.render(mode=True)
        text_actions = world.get_events()
        current_traj_element = {
            "t": env.timestep,
            "score": info["player_0"]["score"],
            "state": str(env.get_json_state_simple(llm_idx)),
            "message": [],
            "mid_action": None,
            "controlled_by_fsm": None,
        }
        for a_i, t_acts in text_actions.items():
            if len(t_acts) > len(agent_text_actions[a_i]):
                logger.debug(f"Agent {a_i} perform text_action {t_acts[len(agent_text_actions[a_i]):]}")
                agent_text_actions[a_i] = t_acts
                traj_infos["text_action"].append({"t": env.timestep, "agent": a_i, "action": t_acts[-1]})

        mid_actions = world.get_mid_actions()

        for a_i, m_acts in mid_actions.items():
            if len(m_acts) > len(agent_mid_actions[a_i]):
                logger.debug(f"Agent {a_i} perform mid_action {m_acts[len(agent_mid_actions[a_i]):]}")
                agent_mid_actions[a_i].append(m_acts[len(agent_mid_actions[a_i])])
                ## each mid_action of LLM has already been saved when generated
                # if a_i != llm_idx:
                #     history_buffer.add_action(agent_mid_actions[a_i][-1], a_i)
                history_buffer.add_action(agent_mid_actions[a_i][-1], a_i)

        ## got a human message
        if human_message:
            logger.success(f"Human: {human_message}")
            history_buffer.add_message(human_message, 1 - llm_idx)

        current_steps = env.timestep
        logger.debug(f"Step {current_steps} / {max_steps}")

        ## improve policy regularly or in case of human message
        if current_steps % urgent_response_interval_n_timestep == 0 or human_message:
            to_react = True

        current_steps = env.timestep
        if current_steps % 100 == 0:
            logger.warning(
                f"Step: {current_steps} / {max_steps}, FPS: {current_steps / (time.time() - episode_s_time): .2f}"
            )

        current_action_right = 0
        human_message = ""

        if current_steps >= max_steps:
            json_state_simple = env.get_json_state_simple(llm_idx)
            logger.error(f"Final Score: {pformat(json_state_simple['total_score'])}")
            break

        await asyncio.sleep(0.25)


async def warm_start():
    s_time = time.time()
    await get_openai_llm_output(MODEL, [{"role": "user", "content": "Hello! Who are you?"}])
    logger.success(f"Warm start time: {time.time() - s_time: .2f}")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, level="SUCCESS")
    f = open("logs/llm_agent_reflexion.log", "w")
    logger.add(f, level="TRACE")
    f = open("logs/llm_agent_reflexion_less.log", "w")
    logger.add(f, level="INFO")
    args, conf, env_conf, _ = parse_args(create_parser())

    # utils.set_random_seed(args.seed)
    utils.set_random_seed(0)

    logger.success("args\n" + pformat(args))
    logger.success("conf\n" + pformat(conf))
    logger.success("env_conf\n" + pformat(env_conf))
    current_action_right: int = 0
    current_steps = 0
    human_message: str = ""
    urgent_response_history_n_event = conf.get("urgent_response_history_n_event", 5)
    urgent_response_interval_n_timestep = conf.get("urgent_response_interval_n_timestep", 25)
    reflection_history_n_event = conf.get("reflection_history_n_event", 15)
    reflection_interval_n_timestep = conf.get("reflection_interval_n_timestep", 75)
    max_steps = env_conf.get("horizon", 1000)  ## 1000 or 500?
    half_max_steps = max_steps // 2
    max_steps = half_max_steps
    to_react = True

    llm_idx = 0
    FSM = args.fsm
    MODEL = args.model
    assert not FSM and not args.no_model, "FSM and no_model cannot be True"
    dir_path = f"results/exp1_2/{env_conf.mode}/reflexion"
    file_path = f"{dir_path}/{MODEL}-{args.seed}.json"
    if os.path.exists(file_path):
        logger.warning(f"File {file_path} already exists, exiting ...")
        sys.exit()

    traj_infos = {
        "traj": [],  # time, state, action, score, message, mid_action
        "urgent_response": [],  # time, input, output, latency
        "reflection": [],  # time, input, output, latency
        "text_action": [],  # time, agent, action
    }
    del env_conf["name"]
    env = OvercookedMaker(**env_conf, display=args.display)
    action_spaces = env.action_spaces
    # control_agent = args.control_agent if args.control_agent is not None else env.players[0]

    text_agent = TextAgent(env._env.unwrapped.world, llm_idx)

    mid_agent = MidAgent(text_agent, env._env.unwrapped.world)
    rule_agent = ReflexionAgentNoFSM(
        text_agent,
        env._env.unwrapped.world,
        send_message=False,
        receive_message=False,
        max_n_react_turn=urgent_response_history_n_event,
        max_n_reflection_event=reflection_history_n_event,
    )

    ## save all history in the buffer
    history_buffer = History(max_steps=max_steps)

    agent_list = [None, None]

    agent_list[llm_idx] = text_agent
    controller = LLMController(action_spaces, agent_list)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(warm_start())
    loop.run_until_complete(asyncio.gather(run_game(), listen_action(), react(), reflection()))

    os.makedirs(f"{os.path.dirname(file_path)}", exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        import json

        json.dump(traj_infos, f)
        logger.error(f"Save in {file_path}")
