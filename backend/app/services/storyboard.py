"""短剧每次只写一种文字。角色、道具、场景、分镜互不混在同一次结果里。"""

import json
import re

from pydantic import BaseModel, Field


class DramaText(BaseModel):
    text: str = Field(min_length=1, max_length=1200)


class DramaShot(BaseModel):
    no: int = Field(ge=1, le=99)
    text: str = Field(min_length=1, max_length=400)


class DramaShots(BaseModel):
    shots: list[DramaShot] = Field(min_length=1, max_length=12)


class DramaOneShot(BaseModel):
    no: int = Field(default=1, ge=1, le=99)
    text: str = Field(min_length=1, max_length=800)


_JSON_RULE = "用户消息里【】后面的文字就是已经连上的材料，必须使用，不要说没收到。只输出一个 JSON 对象，不要 Markdown，不要解释。不要写这一步没要求的内容。"

TASKS: dict[str, str] = {
    "summary": "你是短剧编剧。用户消息里【】后面的文字就是初始创意，必须根据它写这一集在讲什么。不要说没收到创意。不要写角色外貌清单，不要写道具，不要写分镜。" + _JSON_RULE + "字段只有 text。",
    "character": "你是短剧角色设计。只根据已有的剧本摘要写角色画像：脸、发型、服装、体型。不要写分镜情节，不要写道具清单，不要写场景调度。" + _JSON_RULE + "字段只有 text。",
    "prop": "你是短剧道具设计。只写这一集里具体物件的道具提示词：样子、材质、颜色。不要写角色全身，不要写分镜，不要写场景。" + _JSON_RULE + "字段只有 text。没有具体物件时，text 写「这一集没有需要单独出图的道具」。",
    "scene": "你是短剧场景设计。只写场景说明：地点、光线、构图。避免空、左右完全对称、主体死死居中。不要写主角换人，不要写分镜动作，不要写道具清单。" + _JSON_RULE + "字段只有 text。",
    "plot": "你是短剧编剧。只写分镜情节，正好 3 个镜头，一共 9 秒。不要多写，不要少写。不要重写角色外貌，不要写道具提示词。" + _JSON_RULE + '字段只有 shots，正好 3 项，每项有 no 和 text。',
    "shot": "你是短剧分镜。只写其中一镜的画面提示词，给生图用。必须遵守已经给出的角色、场景和道具，不要另造主角。不要重写剧本摘要，不要一次写完全部镜头。" + _JSON_RULE + "字段有 no 和 text。",
}


def system_prompt(task: str) -> str:
    try:
        return TASKS[task]
    except KeyError as exc:
        raise ValueError("不认识的短剧步骤") from exc


def parse_drama(task: str, text: str):
    if task == "plot":
        try:
            data = _load_json(text)
        except ValueError:
            shots = _shots_from_lines(text)
            if not shots:
                raise
            return DramaShots(shots=shots)
        return DramaShots(shots=_shots_from_data(data))
    if task == "shot":
        data = _load_json(text)
        return DramaOneShot.model_validate(data)
    if task not in TASKS:
        raise ValueError("不认识的短剧步骤")
    return DramaText.model_validate(_load_json(text))


def format_drama(task: str, parsed) -> str:
    if task == "summary":
        return f"剧本摘要\n{parsed.text.strip()}"
    if task == "character":
        return f"角色画像\n{parsed.text.strip()}"
    if task == "prop":
        return f"道具提示词\n{parsed.text.strip()}"
    if task == "scene":
        return f"场景说明\n{parsed.text.strip()}"
    if task == "plot":
        lines = ["分镜情节"]
        lines.extend(f"镜头 {shot.no}｜{shot.text.strip()}" for shot in parsed.shots)
        return "\n".join(lines)
    if task == "shot":
        return f"单镜提示词\n镜头 {parsed.no}｜{parsed.text.strip()}"
    raise ValueError("不认识的短剧步骤")


def _shots_from_data(data: dict) -> list[DramaShot]:
    raw = data.get("shots") or data.get("plot") or data.get("scenes") or data.get("storyboard")
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list) or not raw:
        raise ValueError("没有镜头")
    shots = [_shot_from_item(item, index + 1) for index, item in enumerate(raw[:3])]
    if not shots:
        raise ValueError("没有镜头")
    return shots


def _shot_from_item(item: object, index: int) -> DramaShot:
    if isinstance(item, str):
        text = item.strip()[:400]
        if not text:
            raise ValueError("空镜头")
        return DramaShot(no=index, text=text)
    if not isinstance(item, dict):
        raise ValueError("镜头格式不对")
    raw_no = item.get("no") or item.get("index") or item.get("id") or index
    try:
        no = int(raw_no)
    except (TypeError, ValueError):
        no = index
    text = item.get("text") or item.get("visual") or item.get("description") or item.get("content") or item.get("plot") or ""
    text = str(text).strip()[:400]
    if not text:
        raise ValueError("空镜头")
    return DramaShot(no=max(1, min(no, 99)), text=text)


def _shots_from_lines(text: str) -> list[DramaShot]:
    shots: list[DramaShot] = []
    for line in text.splitlines():
        matched = re.match(r"^\s*(?:镜头|分镜)\s*(\d+)\s*[｜|:：]\s*(.+)$", line.strip())
        if not matched:
            continue
        shots.append(DramaShot(no=int(matched.group(1)), text=matched.group(2).strip()[:400]))
    return shots[:12]


def _load_json(text: str) -> dict:
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
    return data
