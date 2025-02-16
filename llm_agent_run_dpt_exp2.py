import asyncio
import os
import random
import sys
import time
from copy import deepcopy
from pprint import pformat

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.biased_agent import (
    AssembleServeAgent,
    PrepareBeefAgent,
    PrepareLettuceAgent,
    SwitchAgent,
)
from agents.comm_infer_llm_agent import CommInferAgent, CommInferAgentNoFSM
from agents.mid_agent import MidAgent
from agents.rule_agent import RuleAgent
from agents.text_agent import TextAgent
from coop_marl.controllers import LLMController
from coop_marl.envs.overcooked.overcooked_maker import OvercookedMaker
from coop_marl.utils import Arrdict
from coop_marl.utils import create_parser_biased_agent as create_parser
from coop_marl.utils import parse_args, utils
from llms.get_llm_output import get_openai_llm_output
from utils.history import History


async def get_biased_agent_action() -> str:
    global current_action_right
    global biased_text_agent, biased_mid_agent
    global beef_agent, lettuce_agent, assemble_serve_agent
    global env
    global history_buffer
    global current_steps, max_steps
    global mid_action_right

    match BIASED_AGENT:
        case 0:
            current_agent = beef_agent
        case 1:
            current_agent = lettuce_agent
        case 2:
            current_agent = assemble_serve_agent
        case 3:
            current_agent = SwitchAgent([0, 250], [beef_agent, lettuce_agent])
        case 4:
            current_agent = SwitchAgent([0, 250], [beef_agent, assemble_serve_agent])
        case 5:
            current_agent = SwitchAgent([0, 250], [lettuce_agent, beef_agent])
        case 6:
            current_agent = SwitchAgent([0, 250], [lettuce_agent, assemble_serve_agent])
        case 7:
            current_agent = SwitchAgent([0, 250], [assemble_serve_agent, beef_agent])
        case 8:
            current_agent = SwitchAgent([0, 250], [assemble_serve_agent, lettuce_agent])
        case 9:
            current_agent = biased_rule_agent

    mid_action_right = None
    current_action_right = None
    n_execution = 0

    while True:
        if current_action_right == None:
            current_action_right = 0
            if not mid_action_right:
                json_state_simple = env.get_json_state_simple(biased_agent_idx)
                logger.info(f"Biased Agent Input {json_state_simple}")
                if isinstance(current_agent, SwitchAgent):
                    mid_action_right = current_agent.get_action(json_state_simple, current_steps)
                else:
                    mid_action_right = current_agent.get_action(json_state_simple)
                if mid_action_right:
                    logger.warning(f"Biased Agent Output {mid_action_right}")
            if mid_action_right:
                end, action_right, status = biased_mid_agent.get_action(mid_action_right[0], **mid_action_right[1])
                n_execution += 1
                if end:
                    if "Failed" in status:
                        logger.success(f"biased agent mid action {status}")
                    else:
                        logger.debug(f"biased agent mid action {status}")
                    mid_action_right = None
                    n_execution = 0
                current_action_right = action_right
            else:
                current_action_right = random.choice([0, 1, 2, 3, 4])
            if n_execution >= 45:
                current_action_right = random.choice([0, 1, 2, 3, 4])
                if n_execution >= 50:
                    mid_action_right = None
                    n_execution = 0

        if current_steps >= max_steps:
            break
        await asyncio.sleep(0.25)


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
            llm_input = rule_agent.get_reflection_llm_input(history)
            logger.debug("Reflection LLM Input")
            logger.debug(llm_input[1]["content"])
            s_time = time.time()
            llm_output = await get_openai_llm_output(MODEL, llm_input)
            e_time = time.time()
            traj_infos["reflection"].append(
                {"t": current_steps, "input": llm_input, "output": llm_output, "latency": e_time - s_time}
            )
            logger.success(f"Reflection LLM Output, Used {e_time - s_time: .4f}s")
            logger.warning(f"Output:\n{llm_output}")
            rule_agent.update_reflection(llm_output)
            to_reflection = False
        if current_steps >= max_steps:
            break
        await asyncio.sleep(1)


async def urgent_response() -> str:
    global rule_agent, env, llm_idx
    global history_buffer
    global urgent_response_history_n_event, urgent_response_interval_n_timestep
    global human_message
    global current_steps, max_steps
    global to_urgent_response
    global MODEL

    while True:
        if to_urgent_response:
            history = history_buffer.get_formatted_history(urgent_response_history_n_event, llm_idx)
            logger.debug("History:\n" + history)
            llm_input = rule_agent.get_urgent_response_llm_input(history)
            logger.debug("Urgent Response LLM Input")
            logger.debug(llm_input[1]["content"])
            s_time = time.time()
            llm_output = await get_openai_llm_output(MODEL, llm_input)
            e_time = time.time()
            traj_infos["urgent_response"].append(
                {"t": current_steps, "input": llm_input, "output": llm_output, "latency": e_time - s_time}
            )
            logger.success(f"Urgent Response LLM Output, Used {e_time - s_time: .4f}s")
            logger.warning(f"Output:\n{llm_output}")
            rule_agent.update_assigned_tasks(llm_output)
            if rule_agent.message:
                history_buffer.add_message(rule_agent.message, llm_idx)
            to_urgent_response = False
        if current_steps >= max_steps:
            break
        await asyncio.sleep(0.1)


async def run_game():
    global current_action_right, human_message
    global text_agent, mid_agent, rule_agent
    global env
    global history_buffer
    global reflection_history_n_event, reflection_interval_n_timestep
    global max_steps, current_steps
    global to_reflection, to_urgent_response

    outcome = env.reset()
    env.render(mode=True)
    dummy_decision = controller.get_prev_decision_view()

    text_agent.update_agent(env._env.unwrapped.world, llm_idx)
    # MARK: world will change after reset
    mid_agent.update(text_agent, env._env.unwrapped.world)
    rule_agent.update(text_agent, env._env.unwrapped.world, env.get_json_state_simple(llm_idx))

    biased_text_agent.update_agent(env._env.unwrapped.world, biased_agent_idx)
    # MARK: world will change after reset
    biased_mid_agent.update(biased_text_agent, env._env.unwrapped.world)

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
        "mid_action": {},
        "controlled_by_fsm": None,
    }
    # init_mid_action = False
    n_execution = 0
    while True:
        decision = Arrdict({p: dummy_decision[p] for p in outcome})
        inp = Arrdict(data=outcome, prev_decision=decision)

        decision = Arrdict()

        for i, k in enumerate(inp.data.keys()):
            if i == llm_idx:
                if not mid_action:
                    current_traj_element["mid_action"][llm_idx] = None
                    json_state_simple = env.get_json_state_simple(llm_idx)

                    if NO_MODEL:
                        s_time = time.time()
                        mid_action = rule_agent.get_action(json_state_simple)
                        traj_infos["urgent_response"].append(
                            {
                                "t": current_steps,
                                "input": str(json_state_simple),
                                "output": str(mid_action),
                                "latency": time.time() - s_time,
                            }
                        )
                        logger.info(f"LLM input {json_state_simple}")
                        logger.success(f"FSM LLM Output: {mid_action}, Used {time.time() - s_time: .4f}s")
                    else:
                        mid_action = rule_agent.get_action(json_state_simple)
                    message_dict = {}
                    history_buffer.add(
                        current_steps,
                        json_state_simple,
                        message_dict,
                    )

                    logger.debug(
                        "History:\n" + pformat([info._asdict() for info in history_buffer.get_history(1)]) + "\n" * 2
                    )
                if mid_action:
                    logger.info(f"DPT Agent: {mid_action}")
                    current_traj_element["mid_action"][llm_idx] = mid_action
                    end, action, status = mid_agent.get_action(mid_action[0], **mid_action[1])
                    n_execution += 1
                    # if init_mid_action and not end:
                    #     init_mid_action = False
                    #     history_buffer.add_action(mid_action, llm_idx)
                    if end:
                        mid_action = None
                        n_execution = 0
                        if "Failed" in status:
                            logger.success(status)
                        else:
                            logger.debug(status)
                if n_execution >= 45:
                    # action = random.choice([0, 1, 2, 3, 4])
                    action = 0
                    if n_execution >= 50:
                        mid_action = None
                        n_execution = 0
                    current_traj_element["controlled_by_fsm"] = False
                else:
                    current_traj_element["controlled_by_fsm"] = rule_agent.controlled_by_fsm
                current_action[i] = action
                decision[k] = Arrdict(action=action)
            else:
                # print(biased_agent_idx, mid_action_right)
                current_traj_element["mid_action"][biased_agent_idx] = mid_action_right
                current_action[i] = current_action_right
                decision[k] = Arrdict(action=current_action_right)
                current_action_right = None
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
            "mid_action": {},
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
                # if a_i != llm_idx:
                #     history_buffer.add_action(agent_mid_actions[a_i][-1], a_i)
                history_buffer.add_action(agent_mid_actions[a_i][-1], a_i)

        if human_message:
            logger.success(f"Human: {human_message}")
            history_buffer.add_message(human_message, 1 - llm_idx)

        current_steps = env.timestep
        logger.debug(f"Step {current_steps} / {max_steps}")

        if current_steps > 0 and current_steps % reflection_interval_n_timestep == 0:
            to_reflection = True
        if current_steps > 0 and (current_steps % urgent_response_interval_n_timestep == 0 or human_message):
            to_urgent_response = True

        current_steps = env.timestep
        if current_steps % 100 == 0:
            logger.warning(
                f"Step: {current_steps} / {max_steps}, FPS: {current_steps / (time.time() - episode_s_time): .2f}"
            )
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


biased_agent_name = {
    0: "BeefAgent",
    1: "LettuceAgent",
    2: "AssembleServeAgent",
    3: "BeefToLettuceAgent",
    4: "BeefToAssembleServeAgent",
    5: "LettuceToBeefAgent",
    6: "LettuceToAssembleServeAgent",
    7: "AssembleServeToBeefAgent",
    8: "AssembleServeToLettuceAgent",
    9: "FSM",
}
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, level="SUCCESS")
    f = open("logs/llm_agent_dpt.log", "w")
    logger.add(f, level="TRACE")
    f = open("logs/llm_agent_dpt_less.log", "w")
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

    reg_env_name = env_conf.name
    urgent_response_history_n_event = conf.get("urgent_response_history_n_event", 5)
    urgent_response_interval_n_timestep = conf.get("urgent_response_interval_n_timestep", 25)
    reflection_history_n_event = conf.get("reflection_history_n_event", 15)
    reflection_interval_n_timestep = conf.get("reflection_interval_n_timestep", 75)

    max_steps = env_conf.get("horizon", 1000)
    half_max_steps = max_steps // 2
    max_steps = half_max_steps

    to_reflection = False
    to_urgent_response = False

    llm_idx = 1
    FSM = args.fsm
    MODEL = args.model
    NO_MODEL = args.no_model
    BIASED_AGENT = args.biased_agent

    dir_path = f"results/exp2/{env_conf.mode}/{biased_agent_name[BIASED_AGENT]}"
    if FSM and args.no_model:
        file_path = f"{dir_path}/FSM-{args.seed}.json"
    elif args.infer_human and FSM:
        file_path = f"{dir_path}/dpt-wtom/{MODEL}-{args.seed}.json"
    elif not args.infer_human and FSM:
        file_path = f"{dir_path}/dpt-wotom/{MODEL}-{args.seed}.json"
    elif args.infer_human and not FSM:
        file_path = f"{dir_path}/dpt-wtom-s2/{MODEL}-{args.seed}.json"
    else:
        file_path = f"{dir_path}/dpt-wotom-s2/{MODEL}-{args.seed}.json"
    if os.path.exists(file_path):
        logger.warning(f"File {file_path} already exists, exiting ...")
        sys.exit()

    traj_infos = {
        "traj": [],  # time, state, action, score, message, mid_action
        "urgent_response": [],  # time, input, output, latency
        "reflection": [],  # time, input, output, latency
        "text_action": [],  # time, agent, action
    }

    mid_action_right = None
    current_traj_element = None

    del env_conf["name"]
    env = OvercookedMaker(**env_conf, display=args.display)
    action_spaces = env.action_spaces
    # control_agent = args.control_agent if args.control_agent is not None else env.players[0]

    text_agent = TextAgent(env._env.unwrapped.world, llm_idx)
    mid_agent = MidAgent(text_agent, env._env.unwrapped.world)

    biased_agent_idx = 0
    biased_text_agent = TextAgent(env._env.unwrapped.world, biased_agent_idx)
    biased_mid_agent = MidAgent(text_agent, env._env.unwrapped.world)
    biased_rule_agent = RuleAgent(biased_text_agent, env._env.unwrapped.world)
    beef_agent = PrepareBeefAgent(biased_text_agent, env._env.unwrapped.world)
    lettuce_agent = PrepareLettuceAgent(biased_text_agent, env._env.unwrapped.world)
    assemble_serve_agent = AssembleServeAgent(biased_text_agent, env._env.unwrapped.world)

    if FSM and args.no_model:
        rule_agent = RuleAgent(
            text_agent,
            env._env.unwrapped.world,
        )
    elif FSM:
        rule_agent = CommInferAgent(
            text_agent,
            env._env.unwrapped.world,
            send_message=args.send_message,
            receive_message=args.receive_message,
            infer_human=args.infer_human,
        )
    else:
        rule_agent = CommInferAgentNoFSM(
            text_agent,
            env._env.unwrapped.world,
            send_message=args.send_message,
            receive_message=args.receive_message,
            infer_human=args.infer_human,
        )

    history_buffer = History(max_steps=max_steps)

    agent_list = [None, None]

    agent_list[llm_idx] = text_agent
    controller = LLMController(action_spaces, agent_list)

    loop = asyncio.get_event_loop()
    if args.no_model:
        loop.run_until_complete(asyncio.gather(run_game(), get_biased_agent_action()))
    else:
        loop.run_until_complete(warm_start())
        loop.run_until_complete(asyncio.gather(run_game(), urgent_response(), reflection(), get_biased_agent_action()))

    os.makedirs(f"{os.path.dirname(file_path)}", exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        import json

        json.dump(traj_infos, f)
        logger.error(f"Save in {file_path}")
