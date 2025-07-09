import re
import os
import backoff
import openai
from loguru import logger

openai_client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

valid_models = [
    "4o-mini",
    "4o",
    "o3-mini-low",
    "gpt-3.5-turbo",
]


model_to_separate_clients = {"your model": "your async openai client"}


@backoff.on_exception(
    backoff.expo,
    (openai.APIError, openai.RateLimitError),
    on_backoff=lambda details: logger.warning(
        f"Model {details['args'][0]} try {details['tries']} times, waiting for {details['wait']} seconds ..."
    ),
    max_tries=5,
)
async def get_openai_llm_output(model: str, messages: list[dict], params: dict = None) -> str:
    assert model in valid_models, f"Invalid model: {model}"
    if params is None:
        params = {"temperature": 0, "max_tokens": 4096, "seed": 0, "top_p": 0.9}
    else:
        logger.error(f"not default params: {params}")

    if model.startswith("o1") or model.startswith("o3"):
        if "max_tokens" in params:
            params["max_completion_tokens"] = params.pop("max_tokens")
        if "temperature" in params:
            params.pop("temperature")
        if "top_p" in params:
            params.pop("top_p")
        for _message in messages:
            if _message["role"] == "system":
                _message["role"] = "user"
        if model.startswith("o3"):
            if model.endswith("-low"):
                params.update({"reasoning_effort": "low"})
                model = model.replace("-low", "")
            elif model.endswith("-medium"):
                params.update({"reasoning_effort": "medium"})
                model = model.replace("-medium", "")
            elif model.endswith("-high"):
                params.update({"reasoning_effort": "high"})
                model = model.replace("-high", "")
    if "-r" in model:
        for _message in messages:
            if _message["role"] == "system":
                _message["role"] = "user"
        if "ollama-" not in model and model not in model_to_separate_clients:
            if "temperature" in params:
                params.pop("temperature")

    if model in model_to_separate_clients:
        client = model_to_separate_clients[model]
        if "gemma2" in model:
            for _message in messages:
                if _message["role"] == "system":
                    system_message = _message["content"]
                    break
            else:
                system_message = ""
            messages = [
                {"role": "user", "content": system_message + _message["content"]}
                for _message in messages
                if _message["role"] == "user"
            ]
    else:
        client = openai_client

    response = await client.chat.completions.create(model=model, messages=messages, **params)
    ret = response.choices[0].message.content
    if "o3" in model:
        logger.warning(
            f'o3 model think length: {response.to_dict()["usage"]["completion_tokens_details"]["reasoning_tokens"]}'
        )
    if "-r" in model and model in model_to_separate_clients:
        ret = "<think>\n" + ret
        logger.warning(f"r1 model think length: {get_think_content_length(ret)}")
    return ret


def get_think_content_length(text):
    match = re.search(r"<think>(.*?)<\/think>", text, re.DOTALL)
    if match:
        content = match.group(1)
        return len(content)
    else:
        return 0


def extract_code_blocks(text, language="json"):
    pattern = rf"```{language}(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches
