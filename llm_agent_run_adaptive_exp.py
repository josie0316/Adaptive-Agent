import asyncio
import os
import sys
import time
from copy import deepcopy
from pprint import pformat

import pygame
from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.adaptive_dpt_agent import AdaptiveDPTAgent, AdaptiveDPTAgentNoFSM
from agents.mid_agent import MidAgent
from agents.text_agent import TextAgent
from coop_marl.controllers import LLMController
from coop_marl.envs.overcooked.overcooked_maker import OvercookedMaker
from coop_marl.utils import Arrdict, create_parser, parse_args, utils
from llms.get_llm_output import get_openai_llm_output
from utils.history import History

# 键盘映射
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

# 实验配置
EXPERIMENT_CONFIGS = {
    "test_round": {
        "duration": 300,  # 5分钟
        "initial_mode": "ai_led",
        "switch_time": 150,  # 2.5分钟后切换
        "button_valid": True,
        "description": "Test round - half AI-led, half Human-led"
    },
    "round_1": {
        "duration": 360,  # 6分钟
        "initial_mode": "human_led",
        "button_valid": True,
        "description": "Round 1 - start Human-led, can switch to AI-led"
    },
    "round_2": {
        "duration": 360,  # 6分钟
        "initial_mode": "ai_led",
        "button_valid": True,
        "description": "Round 2 - start AI-led, can switch to Human-led"
    },
    "round_3": {
        "duration": 360,  # 6分钟
        "initial_mode": "ai_led",  # 随机分配
        "button_valid": False,
        "description": "Round 3 - fake button, no actual switching"
    },
    "round_4": {
        "duration": 360,  # 6分钟
        "initial_mode": "human_led",  # 随机分配
        "button_valid": False,
        "description": "Round 4 - fake button, no actual switching"
    }
}

# 全局变量
current_action_right = 0
human_message = ""
current_steps = 0
max_steps = 1000
to_reflection = False
to_urgent_response = False

# 实验控制变量
current_round = "test_round"
round_start_time = 0
round_config = None
button_click_count = 0
mode_switch_count = 0
last_button_click_time = 0

# 实验数据
experiment_data = {
    "rounds": {},
    "button_clicks": [],
    "mode_switches": [],
    "human_instructions": [],
    "agent_responses": []
}

# 游戏对象
env = None
text_agent = None
mid_agent = None
rule_agent = None
history_buffer = None
controller = None

# 模型配置
MODEL = "gpt-4"
llm_idx = 0


async def listen_action():
    """监听键盘输入"""
    global current_action_right, human_message, current_steps, max_steps
    global button_click_count, last_button_click_time, round_config
    
    while True:
        event = pygame.event.get()
        if len(event) > 0:
            for e in event:
                if e.type == pygame.KEYDOWN:
                    current_action_right = 0
                    
                    # 模式切换按钮 (F1: AI-led, F2: Human-led)
                    if e.key == pygame.K_F1:
                        if round_config and round_config["button_valid"]:
                            success = rule_agent.switch_mode("ai_led")
                            if success:
                                mode_switch_count += 1
                                button_click_count += 1
                                last_button_click_time = time.time()
                                logger.info("Button clicked: Switch to AI-led mode")
                        else:
                            button_click_count += 1
                            last_button_click_time = time.time()
                            logger.info("Fake button clicked: Switch to AI-led mode (no effect)")
                    
                    elif e.key == pygame.K_F2:
                        if round_config and round_config["button_valid"]:
                            success = rule_agent.switch_mode("human_led")
                            if success:
                                mode_switch_count += 1
                                button_click_count += 1
                                last_button_click_time = time.time()
                                logger.info("Button clicked: Switch to Human-led mode")
                        else:
                            button_click_count += 1
                            last_button_click_time = time.time()
                            logger.info("Fake button clicked: Switch to Human-led mode (no effect)")
                    
                    # 动作键
                    elif e.key in KeyToTuple_right:
                        current_action_right = KeyToTuple_right[e.key]
                    
                    # 消息键
                    elif e.key in key_to_message:
                        if e.key in [pygame.K_EQUALS, pygame.K_KP_EQUALS, pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_9, pygame.K_KP9]:
                            human_message = key_to_message[e.key]
                        else:
                            human_message = f"We need {key_to_message[e.key]}"
                
                elif e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

        if current_steps >= max_steps:
            break

        await asyncio.sleep(0.001)


async def urgent_response():
    """紧急响应处理"""
    global rule_agent, env, llm_idx, history_buffer
    global urgent_response_history_n_event, urgent_response_interval_n_timestep
    global human_message, current_steps, max_steps, to_urgent_response, MODEL
    global experiment_data

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
            
            # 记录数据
            experiment_data["agent_responses"].append({
                "type": "urgent_response",
                "round": current_round,
                "step": current_steps,
                "input": llm_input,
                "output": llm_output,
                "latency": e_time - s_time,
                "timestamp": time.time()
            })
            
            logger.success(f"Urgent Response LLM Output, Used {e_time - s_time: .4f}s")
            logger.debug(f"Output:\n{llm_output}")
            rule_agent.update_assigned_tasks(llm_output)
            if rule_agent.message:
                history_buffer.add_message(rule_agent.message, llm_idx)
            to_urgent_response = False
        if current_steps >= max_steps:
            break
        await asyncio.sleep(0.1)


async def reflection():
    """反思处理"""
    global rule_agent, env, llm_idx, history_buffer
    global reflection_history_n_event, reflection_interval_n_timestep
    global current_steps, max_steps, to_reflection, MODEL
    global experiment_data

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
            
            # 记录数据
            experiment_data["agent_responses"].append({
                "type": "reflection",
                "round": current_round,
                "step": current_steps,
                "input": llm_input,
                "output": llm_output,
                "latency": e_time - s_time,
                "timestamp": time.time()
            })
            
            logger.success(f"Reflection LLM Output, Used {e_time - s_time: .4f}s")
            logger.warning("Reflection" + llm_output)
            rule_agent.update_reflection(llm_output)
            to_reflection = False
        if current_steps >= max_steps:
            break
        await asyncio.sleep(1)


def initialize_round(round_name: str):
    """初始化新的round"""
    global current_round, round_config, round_start_time, rule_agent
    global button_click_count, mode_switch_count, experiment_data
    
    current_round = round_name
    round_config = EXPERIMENT_CONFIGS[round_name]
    round_start_time = time.time()
    
    # 重置计数器
    button_click_count = 0
    mode_switch_count = 0
    
    # 设置初始模式
    initial_mode = round_config["initial_mode"]
    if round_name in ["round_3", "round_4"]:
        # 随机分配模式
        import random
        initial_mode = random.choice(["ai_led", "human_led"])
    
    # 重新初始化agent
    rule_agent.switch_mode(initial_mode)
    rule_agent.reset_instruction_state()
    
    # 记录round开始
    experiment_data["rounds"][round_name] = {
        "start_time": round_start_time,
        "initial_mode": initial_mode,
        "button_valid": round_config["button_valid"],
        "description": round_config["description"]
    }
    
    logger.info(f"=== Starting {round_name} ===")
    logger.info(f"Initial mode: {initial_mode}")
    logger.info(f"Button valid: {round_config['button_valid']}")
    logger.info(f"Duration: {round_config['duration']}s")


def check_round_completion():
    """检查round是否完成"""
    global current_round, round_config, round_start_time
    
    if not round_config:
        return False
    
    elapsed_time = time.time() - round_start_time
    
    # 检查test round的特殊切换逻辑
    if current_round == "test_round" and elapsed_time >= round_config["switch_time"]:
        if rule_agent.mode == "ai_led":
            rule_agent.switch_mode("human_led")
            logger.info("Test round: Auto-switching to Human-led mode")
    
    # 检查round是否结束
    if elapsed_time >= round_config["duration"]:
        return True
    
    return False


def get_next_round():
    """获取下一个round"""
    round_sequence = ["test_round", "round_1", "round_2", "round_3", "round_4"]
    try:
        current_index = round_sequence.index(current_round)
        if current_index + 1 < len(round_sequence):
            return round_sequence[current_index + 1]
    except ValueError:
        pass
    return None


async def run_game():
    """主游戏循环"""
    global current_action_right, human_message
    global text_agent, mid_agent, rule_agent, env, history_buffer
    global reflection_history_n_event, reflection_interval_n_timestep
    global max_steps, current_steps, to_reflection, to_urgent_response
    global experiment_data, current_round
    
    # 初始化第一个round
    initialize_round("test_round")
    
    outcome = env.reset()
    env.render(mode=True)
    dummy_decision = controller.get_prev_decision_view()

    text_agent.update_agent(env._env.unwrapped.world, llm_idx)
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

    current_traj_element = {
        "t": 0,
        "state": str(env.get_json_state_simple(llm_idx)),
        "score": 0,
        "message": [],
        "mid_action": None,
        "controlled_by_fsm": None,
        "round": current_round,
        "mode": rule_agent.mode,
    }

    while True:
        decision = Arrdict({p: dummy_decision[p] for p in outcome})
        inp = Arrdict(data=outcome, prev_decision=decision)

        decision = Arrdict()

        for i, k in enumerate(inp.data.keys()):
            if i == llm_idx:
                if not mid_action:
                    current_traj_element["mid_action"] = None
                    json_state_simple = env.get_json_state_simple(llm_idx)

                    if NO_MODEL:
                        s_time = time.time()
                        mid_action = rule_agent.get_action(json_state_simple)
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
                    current_traj_element["mid_action"] = mid_action
                    end, action, status = mid_agent.get_action(mid_action[0], **mid_action[1])
                    
                    if end:
                        mid_action = None
                        if "Failed" in status:
                            logger.success(status)
                        else:
                            logger.debug(status)
                
                current_action[i] = action
                decision[k] = action
            else:
                current_action[i] = current_action_right
                decision[k] = current_action_right
                current_action_right = None

        # 处理人类消息
        if human_message:
            logger.success(f"Human: {human_message}")
            
            # 记录人类指令
            if rule_agent.mode == "human_led":
                experiment_data["human_instructions"].append({
                    "round": current_round,
                    "step": current_steps,
                    "message": human_message,
                    "timestamp": time.time(),
                    "agent_status": rule_agent.get_status()
                })
                
                # 处理人类指令
                rule_agent.receive_human_instruction(human_message)
            
            history_buffer.add_message(human_message, 1 - llm_idx)
            human_message = ""

        # env step
        current_traj_element["action"] = deepcopy(current_action)
        current_traj_element["round"] = current_round
        current_traj_element["mode"] = rule_agent.mode
        current_traj_element["button_clicks"] = button_click_count
        current_traj_element["mode_switches"] = mode_switch_count
        
        experiment_data["rounds"][current_round]["trajectory"] = experiment_data["rounds"].get(current_round, {}).get("trajectory", [])
        experiment_data["rounds"][current_round]["trajectory"].append(current_traj_element)
        
        outcome, info = env.step(Arrdict(action=decision))
        env.render(mode=True)
        text_actions = world.get_events()

        current_traj_element = {
            "t": env.timestep,
            "score": info["player_0"]["score"],
            "state": str(env.get_json_state_simple(llm_idx)),
            "message": [],
            "mid_action": None,
            "controlled_by_fsm": None,
            "round": current_round,
            "mode": rule_agent.mode,
        }

        for a_i, t_acts in text_actions.items():
            if len(t_acts) > len(agent_text_actions[a_i]):
                logger.debug(f"Agent {a_i} perform text_action {t_acts[len(agent_text_actions[a_i]):]}")
                agent_text_actions[a_i] = t_acts
                experiment_data["rounds"][current_round]["text_actions"] = experiment_data["rounds"].get(current_round, {}).get("text_actions", [])
                experiment_data["rounds"][current_round]["text_actions"].append({"t": env.timestep, "agent": a_i, "action": t_acts[-1]})
        
        mid_actions = world.get_mid_actions()

        for a_i, m_acts in mid_actions.items():
            if len(m_acts) > len(agent_mid_actions[a_i]):
                logger.debug(f"Agent {a_i} perform mid_action {m_acts[len(agent_mid_actions[a_i]):]}")
                agent_mid_actions[a_i].append(m_acts[len(agent_mid_actions[a_i])])
                history_buffer.add_action(agent_mid_actions[a_i][-1], a_i)

        current_steps = env.timestep
        logger.debug(f"Step {current_steps} / {max_steps}")

        # 检查round完成
        if check_round_completion():
            next_round = get_next_round()
            if next_round:
                # 保存当前round数据
                experiment_data["rounds"][current_round]["end_time"] = time.time()
                experiment_data["rounds"][current_round]["final_score"] = info["player_0"]["score"]
                experiment_data["rounds"][current_round]["total_button_clicks"] = button_click_count
                experiment_data["rounds"][current_round]["total_mode_switches"] = mode_switch_count
                
                logger.info(f"=== {current_round} completed ===")
                logger.info(f"Final score: {info['player_0']['score']}")
                logger.info(f"Button clicks: {button_click_count}")
                logger.info(f"Mode switches: {mode_switch_count}")
                
                # 初始化下一个round
                initialize_round(next_round)
                
                # 重置环境
                outcome = env.reset()
                env.render(mode=True)
                text_agent.update_agent(env._env.unwrapped.world, llm_idx)
                mid_agent.update(text_agent, env._env.unwrapped.world)
                rule_agent.update(text_agent, env._env.unwrapped.world, env.get_json_state_simple(llm_idx))
                
                # 重置轨迹元素
                current_traj_element = {
                    "t": 0,
                    "state": str(env.get_json_state_simple(llm_idx)),
                    "score": 0,
                    "message": [],
                    "mid_action": None,
                    "controlled_by_fsm": None,
                    "round": current_round,
                    "mode": rule_agent.mode,
                }
            else:
                # 所有round完成
                logger.info("All rounds completed!")
                break

        if current_steps > 0 and current_steps % reflection_interval_n_timestep == 0:
            to_reflection = True
        if current_steps > 0 and (current_steps % urgent_response_interval_n_timestep == 0 or human_message):
            to_urgent_response = True

        current_steps = env.timestep
        if current_steps % 100 == 0:
            logger.warning(
                f"Step: {current_steps} / {max_steps}, FPS: {current_steps / (time.time() - episode_s_time): .2f}"
            )

        if current_steps >= max_steps:
            json_state_simple = env.get_json_state_simple(llm_idx)
            logger.error(f"Final Score: {pformat(json_state_simple['total_score'])}")
            break

        await asyncio.sleep(0.25)


async def warm_start():
    """预热模型"""
    s_time = time.time()
    await get_openai_llm_output(MODEL, [{"role": "user", "content": "Hello! Who are you?"}])
    logger.success(f"Warm start time: {time.time() - s_time: .2f}")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, level="SUCCESS")
    f = open("logs/llm_agent_adaptive.log", "w")
    logger.add(f, level="TRACE")
    f = open("logs/llm_agent_adaptive_less.log", "w")
    logger.add(f, level="INFO")
    
    args, conf, env_conf, _ = parse_args(create_parser())

    utils.set_random_seed(0)

    logger.success("args\n" + pformat(args))
    logger.success("conf\n" + pformat(conf))
    logger.success("env_conf\n" + pformat(env_conf))

    # 实验参数
    urgent_response_history_n_event = conf.get("urgent_response_history_n_event", 5)
    urgent_response_interval_n_timestep = conf.get("urgent_response_interval_n_timestep", 25)
    reflection_history_n_event = conf.get("reflection_history_n_event", 15)
    reflection_interval_n_timestep = conf.get("reflection_interval_n_timestep", 75)

    max_steps = env_conf.get("horizon", 1000)
    half_max_steps = max_steps // 2
    max_steps = half_max_steps

    to_reflection = False
    to_urgent_response = False

    llm_idx = 0
    FSM = args.fsm
    MODEL = args.model
    NO_MODEL = args.no_model

    # 创建结果目录
    dir_path = f"results/adaptive_exp/{env_conf.mode}"
    file_path = f"{dir_path}/adaptive-{args.seed}.json"
    
    if os.path.exists(file_path):
        logger.warning(f"File {file_path} already exists, exiting ...")
        sys.exit()

    # 初始化环境
    del env_conf["name"]
    env = OvercookedMaker(**env_conf, display=args.display)
    action_spaces = env.action_spaces

    text_agent = TextAgent(env._env.unwrapped.world, llm_idx)
    mid_agent = MidAgent(text_agent, env._env.unwrapped.world)

    # 创建AdaptiveDPTAgent
    if FSM:
        rule_agent = AdaptiveDPTAgent(
            text_agent,
            env._env.unwrapped.world,
            initial_mode="ai_led",
            send_message=True,
            receive_message=False,
            infer_human=args.infer_human,
        )
    else:
        rule_agent = AdaptiveDPTAgentNoFSM(
            text_agent,
            env._env.unwrapped.world,
            initial_mode="ai_led",
            send_message=True,
            receive_message=False,
            infer_human=args.infer_human,
        )

    history_buffer = History(max_steps=max_steps)

    agent_list = [None, None]
    agent_list[llm_idx] = text_agent
    controller = LLMController(action_spaces, agent_list)

    # 运行实验
    loop = asyncio.get_event_loop()
    if args.no_model:
        loop.run_until_complete(asyncio.gather(run_game(), listen_action()))
    else:
        loop.run_until_complete(warm_start())
        loop.run_until_complete(asyncio.gather(run_game(), urgent_response(), reflection(), listen_action()))

    # 保存实验结果
    os.makedirs(f"{os.path.dirname(file_path)}", exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        import json
        json.dump(experiment_data, f, indent=2)
        logger.error(f"Save in {file_path}")

    # 输出实验总结
    logger.info("=== Experiment Summary ===")
    for round_name, round_data in experiment_data["rounds"].items():
        logger.info(f"{round_name}: Score={round_data.get('final_score', 0)}, "
                   f"Button clicks={round_data.get('total_button_clicks', 0)}, "
                   f"Mode switches={round_data.get('total_mode_switches', 0)}") 