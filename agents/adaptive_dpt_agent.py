import time
from copy import deepcopy
from typing import Dict, List, Tuple, Union

from gym_cooking.cooking_world.cooking_world import CookingWorld
from loguru import logger

from agents.comm_infer_llm_agent import CommInferAgent
from agents.text_agent import TextAgent


class AdaptiveDPTAgent(CommInferAgent):
    """
    Adaptive DPT Agent that can switch between AI-led and Human-led modes
    """
    
    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        initial_mode: str = "ai_led",
        send_message: bool = False,
        receive_message: bool = False,
        infer_human: bool = False,
        **kwargs
    ) -> None:
        super().__init__(
            text_action_agent, 
            cooking_world,
            send_message=send_message,
            receive_message=receive_message,
            infer_human=infer_human,
            **kwargs
        )
        
        # 模式控制
        self.mode = initial_mode
        self._update_communication_permissions()
        
        # 人类指令处理
        self.human_instruction = None
        self.instruction_received = False
        self.last_instruction_time = None
        
        # 指令映射
        self.instruction_map = {
            "切生菜": ("prepare", {"food": "Lettuce", "plate": True}),
            "煎牛排": ("prepare", {"food": "Beef", "plate": True}),
            "组装汉堡": ("assemble", {"food": "BeefBurger"}),
            "上菜": ("serve", {"food": "BeefBurger"}),
            "灭火": ("putout_fire", {}),
            "Lettuce": ("prepare", {"food": "Lettuce", "plate": True}),
            "Beef": ("prepare", {"food": "Beef", "plate": True}),
            "Serve": ("serve", {"food": "BeefBurger"}),
            "Fire": ("putout_fire", {}),
            "LettuceBurger": ("assemble", {"food": "LettuceBurger"}),
            "BeefBurger": ("assemble", {"food": "BeefBurger"}),
            "BeefLettuceBurger": ("assemble", {"food": "BeefLettuceBurger"}),
            "Bread": ("prepare", {"food": "Bread", "plate": False}),
            "Plate": ("prepare", {"food": "Plate", "plate": False}),
        }
        
        # 状态跟踪
        self.current_action = None
        self.action_execution_count = 0
        
        logger.info(f"AdaptiveDPTAgent initialized with mode: {self.mode}")
        logger.info(f"Communication: send={self.send_message}, receive={self.receive_message}")
    
    def _update_communication_permissions(self):
        """根据当前模式更新通信权限"""
        if self.mode == "ai_led":
            self.send_message = True
            self.receive_message = False
        elif self.mode == "human_led":
            self.send_message = False
            self.receive_message = True
        else:
            logger.error(f"Invalid mode: {self.mode}")
    
    def switch_mode(self, new_mode: str):
        """切换模式"""
        if new_mode not in ["ai_led", "human_led"]:
            logger.error(f"Invalid mode: {new_mode}")
            return False
        
        old_mode = self.mode
        self.mode = new_mode
        self._update_communication_permissions()
        
        # 清除指令状态
        self.human_instruction = None
        self.instruction_received = False
        self.last_instruction_time = None
        
        logger.info(f"Mode switched: {old_mode} -> {new_mode}")
        logger.info(f"Communication updated: send={self.send_message}, receive={self.receive_message}")
        return True
    
    def receive_human_instruction(self, message: str):
        """接收人类指令（仅在human_led模式下有效）"""
        if self.mode != "human_led":
            logger.warning(f"Received human instruction in {self.mode} mode: {message}")
            return False
        
        if not self.receive_message:
            logger.warning(f"Agent not configured to receive messages: {message}")
            return False
        
        self.last_instruction_time = time.time()
        
        # 解析指令
        for key, action in self.instruction_map.items():
            if key in message:
                self.human_instruction = action
                self.instruction_received = True
                logger.info(f"[HUMAN-LED] AI received instruction: '{key}' -> {action}")
                return True
        
        logger.warning(f"[HUMAN-LED] AI cannot understand instruction: {message}")
        return False
    
    def _check_urgent_situation(self, json_state: Dict) -> bool:
        """
        只在真正有火灾时返回 True
        """
        # 只判断 ("Fire", "")
        fire_count = json_state.get("objects", {}).get(("Fire", ""), 0)
        if fire_count > 0:
            logger.info(f"[URGENT] Fire detected! fire_count={fire_count}")
            return True
        return False
    
    def _handle_urgent_situation(self, json_state: Dict) -> Tuple[str, Dict]:
        """处理紧急情况"""
        objects = json_state.get("objects", {})
        # Only trigger if there is an actual fire (not just a fire object)
        if objects.get(("Fire", ""), 0) > 0:
            logger.warning("[URGENT] Fire detected! Switching to fire extinguishing mode.")
            return ("putout_fire", {})
        return super().get_action(json_state)
    
    def get_action(self, json_state: Dict) -> Tuple[str, Dict]:
        """
        优化决策逻辑：紧急情况>人类指令>LLM
        """
        logger.info(f"get_action called, mode={self.mode}, instruction_received={self.instruction_received}")
        # 1. 紧急情况优先
        if self._check_urgent_situation(json_state):
            action = self._handle_urgent_situation(json_state)
            self.current_action = action
            logger.info(f"[URGENT] Executing emergency action: {action}")
            return action
        # 2. human-led 且有指令
        if self.mode == "human_led" and self.instruction_received:
            action = self.human_instruction
            self.instruction_received = False  # 清除指令
            self.current_action = action
            self.action_execution_count += 1
            if self.last_instruction_time:
                response_time = time.time() - self.last_instruction_time
                logger.info(f"[HUMAN-LED] Executing human instruction: {action} (response time: {response_time:.3f}s)")
            else:
                logger.info(f"[HUMAN-LED] Executing human instruction: {action}")
            return action
        # 3. 其他情况都走 LLM
        logger.info(f"[LLM] Calling super().get_action for LLM decision (mode={self.mode})")
        action = super().get_action(json_state)
        self.current_action = action
        logger.info(f"[LLM] LLM decision: {action}")
        return action
    
    def get_status(self) -> Dict:
        """获取当前状态信息"""
        return {
            "mode": self.mode,
            "send_message": self.send_message,
            "receive_message": self.receive_message,
            "has_human_instruction": self.instruction_received,
            "current_action": self.current_action,
            "action_execution_count": self.action_execution_count,
            "last_instruction_time": self.last_instruction_time
        }
    
    def reset_instruction_state(self):
        """重置指令状态"""
        self.human_instruction = None
        self.instruction_received = False
        self.last_instruction_time = None
        logger.debug("Instruction state reset")


class AdaptiveDPTAgentNoFSM(AdaptiveDPTAgent):
    """
    Adaptive DPT Agent without FSM (继承自CommInferAgentNoFSM)
    """
    
    def __init__(
        self,
        text_action_agent: TextAgent,
        cooking_world: CookingWorld,
        initial_mode: str = "ai_led",
        send_message: bool = False,
        receive_message: bool = False,
        infer_human: bool = False,
        **kwargs
    ) -> None:
        # 直接调用AdaptiveDPTAgent的初始化，但使用NoFSM的父类
        from agents.comm_infer_llm_agent import CommInferAgentNoFSM
        
        # 临时替换父类
        original_parent = AdaptiveDPTAgent.__bases__
        AdaptiveDPTAgent.__bases__ = (CommInferAgentNoFSM,)
        
        try:
            super().__init__(
                text_action_agent, 
                cooking_world,
                send_message=send_message,
                receive_message=receive_message,
                infer_human=infer_human,
                **kwargs
            )
        finally:
            # 恢复原始父类
            AdaptiveDPTAgent.__bases__ = original_parent
        
        # 重新设置模式
        self.mode = initial_mode
        self._update_communication_permissions() 