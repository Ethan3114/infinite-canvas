"""把模型返回的文字收成固定字段的生成卡。格式不对就再试一次，仍不对就失败。"""

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

PROMPT_PATH = Path(__file__).parent / "prompts" / "generation_card.txt"


class GenerationCard(BaseModel):
    product_appearance: str = Field(min_length=1, max_length=400)
    scene_and_light: str = Field(min_length=1, max_length=400)
    style: str = Field(min_length=1, max_length=200)
    must_not: str = Field(min_length=1, max_length=300)
    prompt: str = Field(min_length=1, max_length=1200)


@lru_cache
def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def parse_card(text: str, image_type: str) -> GenerationCard:
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("没有 JSON")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("不是对象")
    card = GenerationCard.model_validate(data)
    # 图类型以用户在页面上的选择为准，不让模型改掉。
    if image_type == "主图" and "干净" not in card.scene_and_light and "白" not in card.scene_and_light:
        card.scene_and_light = f"干净背景，棚拍光。{card.scene_and_light}"
    return card


def image_prompt(card: GenerationCard) -> str:
    text = card.prompt.strip()
    if card.must_not and card.must_not not in text:
        text = f"{text} 不要出现：{card.must_not}"
    return text
