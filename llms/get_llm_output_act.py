import re
import traceback
from enum import Enum
from typing import Literal, Union

import openai
from loguru import logger
from pydantic import BaseModel

valid_models = [
    # openai
    "4o-mini",
    "4o",
    "o3-mini",
    "gpt-3.5-turbo",
]


class RawFoodParam(str, Enum):
    LETTUCE = "Lettuce"
    BEEF = "Beef"
    BREAD = "Bread"


class AssembledFoodParam(str, Enum):
    BEEF_LETTUCE = "BeefLettuce"
    LETTUCE_BURGER = "LettuceBurger"
    BEEF_BURGER = "BeefBurger"
    BEEF_LETTUCE_BURGER = "BeefLettuceBurger"


class ThingStatusPairParam(str, Enum):
    PLATE_EMPTY = "Plate_"
    LETTUCE_UNCHOPPED = "Lettuce_fresh"
    LETTUCE_CHOPPED = "Lettuce_done"
    BEEF_FRESH = "Beef_fresh"
    BEEF_WELL_COOKED = "Beef_done"
    BREAD = "Bread_"
    BEEF_LETTUCE = "BeefLettuce_"
    BEEF_BURGER = "BeefBurger_"
    LETTUCE_BURGER = "LettuceBurger_"
    BEEF_LETTUCE_BURGER = "BeefLettuceBurger_"
    FIRE_EXTINGUISHER = "FireExtinguisher_"


class ActionBase(BaseModel):
    type: str


class prepare(ActionBase):
    type: Literal["prepare"]
    food: RawFoodParam
    plate: bool | None = None


class assemble(ActionBase):
    type: Literal["assemble"]
    food: AssembledFoodParam


class serve(ActionBase):
    type: Literal["serve"]
    food: AssembledFoodParam


class putout_fire(ActionBase):
    type: Literal["putout_fire"]


class pass_on(ActionBase):
    type: Literal["pass_on"]
    thing_status_pair: ThingStatusPairParam


class clean_a_counter(ActionBase):
    type: Literal["clean_a_counter"]


class Action(BaseModel):
    # action: Union[prepare, assemble, serve, putout_fire, pass_on, clean_a_counter] = Field(..., discriminator="type")
    action: prepare | assemble | serve | putout_fire | pass_on | clean_a_counter


openai_client = openai.AsyncOpenAI(base_url="http://localhost:40000", api_key="sk-1234")

ollama_client = openai.AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="sk-1234")


model_to_deepseek_clients = {
    "deepseek-r1:70b": openai.AsyncOpenAI(base_url="http://path/to/your/llama.cpp/server", api_key="sk-1234"),
    "deepseek-r1:32b": openai.AsyncOpenAI(base_url="http://path/to/your/llama.cpp/server", api_key="sk-1234"),
    "deepseek-r1:14b": openai.AsyncOpenAI(base_url="http://path/to/your/llama.cpp/server", api_key="sk-1234"),
    "deepseek-r1:8b": openai.AsyncOpenAI(base_url="http://path/to/your/llama.cpp/server", api_key="sk-1234"),
    "deepseek-r1:7b": openai.AsyncOpenAI(base_url="http://path/to/your/llama.cpp/server", api_key="sk-1234"),
}


def check_client_alive(client: openai.OpenAI) -> bool:
    try:
        client.models.list()
        return True
    except (openai.APIConnectionError, openai.APIError, Exception):
        return False


async def get_openai_llm_output(messages: list[dict[str, str]], model: str, params: dict) -> Union[Action, None]:
    assert model in valid_models, f"Invalid model: {model}"

    if params is None or len(params) == 0:
        params = {"temperature": 0, "max_tokens": 4096, "seed": 0, "top_p": 0.9}
    else:
        logger.error(f"not default params: {params}")

    if "ollama-deepseek-r1" in model:
        try:
            model = model.replace("ollama-", "")
            client = model_to_deepseek_clients[model]
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += "\nBe as brief as possible in your <think> part, less than 250 characters."
                    break
            else:
                messages = [
                    {
                        "role": "system",
                        "content": "Be as brief as possible in your <think> part, less than 250 characters.",
                    },
                    *messages,
                ]
            completion = await client.chat.completions.create(model=model, messages=messages, **params)
            content = completion.choices[0].message.content
            logger.trace(f"Deepseek-r1 response: {content}")
            pattern = r"<think>(.*?)<\/think>(.*)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                think_content = match.group(1).strip()
                logger.warning(f"r1 model think length: {len(think_content)}")
                after_content = match.group(2).strip()
                return Action.model_validate_json(after_content)
            else:
                return Action.model_validate_json(content)

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    if "o1" in model or "o3" in model:
        if model not in ["o1-mini"]:
            params.update({"reasoning_effort": "low"})
        if "max_tokens" in params:
            params["max_completion_tokens"] = params.pop("max_tokens")
        if "temperature" in params:
            params.pop("temperature")
        if "top_p" in params:
            params.pop("top_p")

    if "ollama-" in model:
        model = model.replace("ollama-", "")
        if model in model_to_deepseek_clients:
            client = model_to_deepseek_clients[model]
        else:
            client = ollama_client

    else:
        client = openai_client

    try:
        completion = await client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=Action,
            **params,
        )

        friends_response = completion.choices[0].message
        if "o3" in model:
            logger.warning(
                f'o3 model think length: {friends_response.to_dict()["usage"]["completion_tokens_details"]["reasoning_tokens"]}'
            )
        if friends_response.parsed:
            return friends_response.parsed
        else:
            logger.warning(f"Invalid response: {friends_response.refusal}")
            return None
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None
