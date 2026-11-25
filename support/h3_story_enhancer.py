import json
import logging
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .h3_system_prompts import (
    ALIGNMENTS, BASE_FIELDS, MODE_GUIDES, PRESERVE_BRIEF, REF_FIELDS, REF_TASKS, STAGING, writing_system_prompt,
)


_MODES = {
    "1ref2va": "One reference asset supplies identity, appearance, action, style, or sound.",
    "2ref2va": "Two reference assets supply independently stated attributes or jointly define a subject.",
    "Nref2va": "Three or more reference assets supply individually mapped roles.",
    "i2va": "Picture 1 is the actual first frame.",
    "flf2va": "Pictures 1 and 2 are the actual first and last frames (MiniMax FL2VA).",
    "l2va": "Picture 1 is the actual last frame only.",
    "t2va": "Text-only audiovisual generation with no media anchors.",
}
H3_MODES = ("off", "auto", *_MODES)

_SUPPORT_DIR = Path(__file__).resolve().parent
_T8_CATALOG = _SUPPORT_DIR.parent / "minimax-h3-prompt-skill-T8" / "catalog" / "template-index.json"
_STANDALONE_TEMPLATES = {"stage-two-turn-pause-reaction", "build-earned-arrival-journey"}
_logger = logging.getLogger("llama-cpp_vlm")

def _keywords(text):
    words = set()
    for word in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", text.lower()):
        if word.isascii():
            if len(word) >= 3:
                words.add(word)
        else:
            words.update(word[i:i + 2] for i in range(len(word) - 1))
    return words


@lru_cache(maxsize=1)
def _template_index():
    bundled = json.loads((_SUPPORT_DIR / "h3_templates.json").read_text(encoding="utf-8"))
    try:
        source = json.loads(_T8_CATALOG.read_text(encoding="utf-8"))
        cards = []
        for entity in source["recommendationEntities"]:
            card = entity["card"]
            if "MiniMax H3" in card["models"]:
                cards.append({
                    "id": entity["templateId"],
                    "title": card["titleEn"],
                    "title_zh": card["titleZh"],
                    "tags": card["tags"],
                    "mechanism": card["mechanismEn"],
                    "mechanism_zh": card["mechanismZh"],
                    "anchors": card["requiredAnchorsZh"],
                })
        if not cards:
            raise ValueError("no MiniMax H3 templates in recommendationEntities")
        missing_standalone = _STANDALONE_TEMPLATES - {card["id"] for card in cards}
        cards.extend(card for card in bundled if card["id"] in missing_standalone)
        return _index_cards(cards)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _logger.warning("Could not use the local T8 catalog at %s. Using bundled templates. %s", _T8_CATALOG, exc)
    return _index_cards(bundled)


def _index_cards(cards):
    indexed = []
    frequency = Counter()
    for card in cards:
        title_terms = _keywords(" ".join([card["title"], card["title_zh"], *card["tags"]]))
        terms = title_terms | _keywords(" ".join([card["mechanism"], card["mechanism_zh"], *card["anchors"]]))
        indexed.append((card, title_terms, terms))
        frequency.update(terms)
    return indexed, frequency


def _search_templates(brief):
    indexed, frequency = _template_index()
    query = _keywords(brief)
    matches = []
    for card, title_terms, terms in indexed:
        score = sum((2 if term in title_terms else 1) / frequency[term] for term in sorted(query & terms))
        if score:
            matches.append((score, card))
    matches.sort(key=lambda match: match[0], reverse=True)
    return [card for _, card in matches[:8]]


def _unwrap_fence(text):
    fenced = re.fullmatch(r"```(?:[a-zA-Z]+)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    return fenced.group(1).strip() if fenced else text


def _stage_answer(complete, stage, guide, brief, *, history=(), media=()):
    user_content = [{"type": "text", "text": brief}, *media] if media else brief
    messages = [{"role": "system", "content": guide}, *history, {"role": "user", "content": user_content}]
    answer, reason = complete(messages, stage)
    if reason == "length":
        raise RuntimeError(f"{stage} reached a generation limit. Check max_tokens and the context (n_ctx).")
    if not answer:
        raise RuntimeError(f"{stage} returned no usable answer. Check the chat template and token budget.")
    return _unwrap_fence(answer)


def _format_issue(prompt, mode, fields):
    headers = list(re.finditer(r"^([a-z_]+):", prompt, flags=re.MULTILINE))
    if tuple(header[1] for header in headers) != fields:
        return f"Write exactly these fields in order: {', '.join(fields)}."
    alignment = prompt[:headers[0].start()].strip()
    if mode in ALIGNMENTS:
        expected = re.escape(ALIGNMENTS[mode])
        expected = expected.replace(re.escape("Shot N"), r"Shot [1-9]\d*").replace(re.escape("S.SS"), r"\d+\.\d{2}")
        if not re.fullmatch(expected, alignment):
            return "Use the required opening alignment line with the actual shot index and two-decimal duration."
    elif alignment:
        return f"Start directly with {fields[0]}:."

    ends = [header.start() for header in headers[1:]] + [len(prompt)]
    sections = {header[1]: prompt[header.end():end].strip() for header, end in zip(headers, ends)}
    empty = [field for field, body in sections.items() if not body]
    if empty:
        return f"Complete the empty fields: {', '.join(empty)}."
    if fields == REF_FIELDS:
        prefix = re.match(r"\[([^\]]+)\]\s+\S", sections["summary"])
        if not prefix or any(task not in REF_TASKS for task in prefix[1].split(" + ")):
            return "Start the summary body with the H3 task prefix, such as [reference generation]."
    return None


def _normalize_format(prompt, fields, task_types):
    names = "|".join(fields)
    # Accept plain headers and either common placement of Markdown bold markers.
    header = rf"^[ \t]*(?:\*\*({names})[ \t]*:\*\*|\*\*({names})\*\*[ \t]*:|({names})[ \t]*:)"
    plain_fields = set(re.findall(r"^([a-z_]+):", prompt, flags=re.MULTILINE))

    def normalize_header(match):
        name = (match[1] or match[2] or match[3]).lower()
        return match[0] if name in plain_fields else name + ":"

    prompt = re.sub(header, normalize_header, prompt, flags=re.MULTILINE | re.IGNORECASE)
    if fields != REF_FIELDS:
        return prompt

    summary = re.search(r"^summary:(.*?)(?=^[a-z_]+:|\Z)", prompt, flags=re.MULTILINE | re.DOTALL)
    if not summary or not summary[1].strip():
        return prompt
    body = summary[1].lstrip()
    offset = summary.end(1) - len(body)
    bracket = re.match(r"\[([^\]]+)\]", body)
    if bracket:
        # Preserve the model's explicit task selection and normalize its spelling.
        tasks = [part.strip().lower() for part in bracket[1].split("+")]
        if all(task in REF_TASKS for task in tasks):
            content = body[bracket.end():]
            if not content.strip():
                # Supply a missing summary sentence from the draft itself.
                detail = re.search(r"^detailed_description:(.*?)(?=^[a-z_]+:|\Z)", prompt, flags=re.MULTILINE | re.DOTALL)
                description = re.sub(r"^\[Shot 1\]\s*", "", detail[1].strip()) if detail else ""
                sentence = re.search(r"[^\n.!?][^\n]*?[.!?](?=\s|$)", description)
                if not sentence or not 24 <= len(sentence[0]) <= 350 or "<d>" in sentence[0]:
                    return prompt
                content = sentence[0] + content
            return prompt[:offset] + "[" + " + ".join(tasks) + "] " + content.lstrip() + prompt[summary.end(1):]
    elif not body.startswith("[") and isinstance(task_types, list) and task_types and all(task in REF_TASKS for task in task_types):
        # The router has already identified the role, so no text needs regenerating.
        separator = " " if offset == summary.start(1) else ""
        return prompt[:offset] + separator + "[" + " + ".join(dict.fromkeys(task_types)) + "] " + prompt[offset:]
    return prompt


def enhance_story(mode, user_content, history, complete, *, video_input):
    if mode not in H3_MODES[1:]:
        raise ValueError(f"Unknown H3_story_enhancer mode: {mode}")

    if isinstance(user_content, str):
        brief, media = user_content.strip(), []
    else:
        brief = "\n".join(part["text"] for part in user_content if part["type"] == "text").strip()
        media = [part for part in user_content if part["type"] == "image_url"]
    if not brief:
        raise ValueError("H3_story_enhancer requires a story in custom_prompt.")
    if video_input and media:
        media_note = f"The attached {len(media)} sampled frames represent one video reference in chronological order (<Video 1>)."
    else:
        media_note = f"Attached images: {len(media)}. Their order is the picture index. The brief can also name assets supplied downstream."
    story = f"{media_note}\n\nOriginal brief:\n{brief}"

    candidates = _search_templates(brief)
    choices = "\n".join(f"{idx}. {card['title']} / {card['title_zh']}" for idx, card in enumerate(candidates, 1))
    modes = "\n".join(f"{name}: {definition}" for name, definition in _MODES.items())
    route = _stage_answer(complete, "H3 routing", f"""Choose the generation mode and one reusable story pattern for the brief. Return only a JSON object with mode (string), template (integer), and task_types (array of strings). Pick 0 for template when none fits the original plot and timing.
The node's mode setting is {mode}. Use that mode exactly when it is fixed. For auto, choose one of the modes below. Distinguish identity or style references from explicitly anchored opening/ending frames. Attached images without an explicit frame role are reference assets. Count named downstream assets as well as attachments without double-counting. A sampled video is one source asset.
For Ref2VA fill task_types with the roles clearly established by the brief. Use only: {', '.join(REF_TASKS)}. An appearance-only reference is ["reference generation"]. Use [] when the role is uncertain or the mode is not Ref2VA.
{modes}
Candidate story patterns:
0. No pattern
{choices}""", story)
    try:
        selection = json.loads(route)
    except json.JSONDecodeError as exc:
        raise RuntimeError("H3 routing must return a JSON object with a mode and template number.") from exc
    if not isinstance(selection, dict):
        raise RuntimeError("H3 routing returned invalid metadata.")
    if mode == "auto":
        mode = selection.get("mode")
        if not isinstance(mode, str) or mode not in _MODES:
            raise RuntimeError("H3 routing returned an unknown mode. Select the H3 mode manually or retry.")
    template = selection.get("template")
    pattern = "Use the brief's own story structure."
    if type(template) is int and 1 <= template <= len(candidates):
        card = candidates[template - 1]
        anchors = " / ".join(card["anchors"])
        pattern = f"{card['title']}: {card['mechanism']}\nStructure cues: {anchors}"

    plan = _stage_answer(complete, "H3 story planning", f"""Turn the brief into a concise shooting plan in the user's language. Use the supplied pattern only where it supports the story. Preserve the user's intent over any template cue. Give each beat a visible action and consequence, coherent staging, a motivated camera decision and sound when useful. Map each line to its speaker and each reference to its requested role. Leave unspecified visual traits of unseen assets for the writing stage. Return the plan only.
{PRESERVE_BRIEF}
{STAGING}
Mode: {_MODES[mode]} {MODE_GUIDES[mode]}
Story pattern: {pattern}""", story)

    fields = REF_FIELDS if mode.endswith("ref2va") else BASE_FIELDS
    writing_guide = writing_system_prompt(mode, fields)
    prompt = _stage_answer(complete, "H3 prompt writing", writing_guide, f"{story}\n\nShooting plan:\n{plan}", history=history, media=media)
    task_types = selection.get("task_types")
    issue = _format_issue(prompt, mode, fields)
    if issue:
        normalized = _normalize_format(prompt, fields, task_types)
        if not _format_issue(normalized, mode, fields):
            _logger.info("H3 applied local formatting to the %s prompt.", mode)
            return normalized
        _logger.info("H3 format correction requested for %s: %s", mode, issue)
        repair = f"{writing_guide}\n\nCorrect the draft's output format. {issue} Keep its established visuals and the original brief."
        prompt = _stage_answer(complete, "H3 format correction", repair, f"{story}\n\nDraft:\n{prompt}")
        issue = _format_issue(prompt, mode, fields)
        if issue:
            prompt = _normalize_format(prompt, fields, task_types)
            issue = _format_issue(prompt, mode, fields)
            if issue:
                raise RuntimeError(f"H3 format correction returned an invalid {mode} prompt. {issue}")
    return prompt
