import json
import logging
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path


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

_BASE_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
_REF_FIELDS = ("subject_definitions", "summary", "retention_analysis", "detailed_description", *_BASE_FIELDS[1:])
_ALIGNMENTS = {
    "i2va": "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.",
    "flf2va": "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.",
    "l2va": "How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.",
}
_MODE_GUIDES = {
    "1ref2va": "Bind the requested attributes to the one supplied asset. An appearance reference can define one or more <Subject N> entries. Only create entries for content with an actual role.",
    "2ref2va": "Map both assets explicitly. Keep identities separate when they represent different people; combine the sources only when they define the same subject or supply different attributes of that subject.",
    "Nref2va": "Map each used asset and its distinct role, including which shots it affects. Number pictures, videos and audio separately. Keep character identities, reference features and assigned roles consistent across cuts.",
    "i2va": "Open on the exact framing, pose and spatial layout of Picture 1. Show a plausible onset of motion and a visible consequence without resetting the scene.",
    "flf2va": "Plan a visible chain of intermediate poses, prop states and framing changes that physically links the two images. Use one continuous shot by default and reach Picture 2 at the end.",
    "l2va": "Work backward from Picture 1 to plan a plausible opening. Bring the moving subject, props and framing into alignment with the last frame.",
    "t2va": "Build all visible subjects, action and sound from the brief. Establish the scene without reference labels or a frame-alignment line.",
}

_PRESERVE_BRIEF = """The original brief is authoritative for plot, cast, required actions, constraints, requested duration, and dialogue. Preserve exact lines, lyrics, and visible text verbatim in their original language. Use examples as inspiration when they are labeled as examples. Preserve a request for silence. Keep explicit duration, or use 15 seconds when omitted. Fill only gaps needed to make the scene clear and filmable."""

_SHOT_GUIDE = """Write the prompt in English apart from speech, lyrics and visible text. Make each beat observable through blocking, gaze, physical actions, composition, light, and synchronized sound. Keep identities, clothing, props and spatial relationships consistent. Make required actions visible from onset to result. Prefer a clear hook, progression, and closing reaction when the story permits. Start with [Shot 1] without a timestamp. Start any later [Shot N] with an increasing cut time such as At 00:04.200, inside the duration. Use motivated cuts and specify useful camera moves in the shot prose.
Assign (S1), (S2), etc. by first actual vocal event and keep them stable independently of <Subject N>. Use <d>[language name] spoken words</d>, for example <d>[Chinese] 我等你。</d>. Keep quotation marks that merely delimit the line, acting directions, and gestures outside the tag. Put visible text in double quotes. Put dialogue and diegetic audio in the shot narrative. Limit overall_soundscape to ambience, physical sounds, and nonverbal sounds. Describe audience-only music in non_diegetic_music or use N/A when there is none."""

_REF_TASKS = ("reference generation", "keyframe completion", "video continuation", "video editing", "audio reuse", "audio reference")
_REF_GUIDE = """Define each reusable visible element as <Subject N> with its asset provenance. Define a standalone <Picture N> only for a structural image anchor, <Video N> for the whole-video role, and <Audio N> for reused or referenced audio. Keep these labels in angle brackets throughout.
Begin the summary body with the task in brackets, for example summary: [reference generation] ... for identity or style guidance. Put task labels only in this summary prefix. Use the roles that apply from reference generation, keyframe completion, video continuation, video editing, audio reuse, and audio reference. Join multiple roles with ' + ' inside the same brackets.
In retention_analysis, put each definition on its own line with its shot coverage and retention marker (fully_preserved, partially_preserved, attribute_transfer or weak_reference for visual content). Describe audio reuse versus audio guidance as appropriate. A change of pose, location, or framing alone preserves identity. Keep asset references at the corresponding action or sound in detailed_description."""


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
    if mode in _ALIGNMENTS:
        expected = re.escape(_ALIGNMENTS[mode])
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
    if fields == _REF_FIELDS:
        prefix = re.match(r"\[([^\]]+)\]\s+\S", sections["summary"])
        if not prefix or any(task not in _REF_TASKS for task in prefix[1].split(" + ")):
            return "Start the summary body with the H3 task prefix, such as [reference generation]."
    return None


def enhance_story(mode, user_content, history, system_prompt, complete, *, video_input):
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
    route = _stage_answer(complete, "H3 routing", f"""Choose the generation mode and one reusable story pattern for the brief. Return only a JSON object with keys mode (string) and template (integer). Pick 0 for template when none fits the original plot and timing.
The node's mode setting is {mode}. Use that mode exactly when it is fixed. For auto, choose one of the modes below. Distinguish identity or style references from explicitly anchored opening/ending frames. Attached images without an explicit frame role are reference assets. Count named downstream assets as well as attachments without double-counting. A sampled video is one source asset.
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

    plan = _stage_answer(complete, "H3 story planning", f"""Turn the brief into a concise shooting plan in the user's language. Use the supplied pattern only where it supports the story. Preserve the user's intent over any template cue. Give each beat a visible action and consequence, coherent staging, a motivated camera decision and sound when useful. Track reference roles, dialogue, and continuity. Check that actions and dialogue fit the requested runtime. Return the plan only.
{_PRESERVE_BRIEF}
Mode: {_MODES[mode]} {_MODE_GUIDES[mode]}
Story pattern: {pattern}""", story)

    fields = _REF_FIELDS if mode.endswith("ref2va") else _BASE_FIELDS
    format_guide = "Return exactly these fields in order: " + ", ".join(field + ":" for field in fields)
    if mode in _ALIGNMENTS:
        format_guide += f"\nStart with this alignment line followed by a blank line; resolve N to the last shot index and S.SS to the duration (two decimals):\n{_ALIGNMENTS[mode]}"
    if fields == _REF_FIELDS:
        format_guide += f"\n{_REF_GUIDE}"
    style = f"\nAdditional style preferences (apply only if compatible with the H3 format and original brief):\n{system_prompt}" if system_prompt.strip() else ""
    writing_guide = f"""Write one ready-to-use MiniMax H3 prompt for {mode}. Use the shooting plan for staging and camera details and the original brief to verify facts and required lines. Check timing, continuity, asset roles and exact dialogue before answering. Output only the prompt, with no title, commentary, or markdown fences.
{_PRESERVE_BRIEF}
{_MODE_GUIDES[mode]}
{_SHOT_GUIDE}
{format_guide}{style}"""
    prompt = _stage_answer(complete, "H3 prompt writing", writing_guide, f"{story}\n\nShooting plan:\n{plan}", history=history, media=media)
    issue = _format_issue(prompt, mode, fields)
    if issue:
        repair = f"{writing_guide}\n\nCorrect the draft's output format. {issue} Keep its established visuals and the original brief."
        prompt = _stage_answer(complete, "H3 format correction", repair, f"{story}\n\nDraft:\n{prompt}")
        issue = _format_issue(prompt, mode, fields)
        if issue:
            raise RuntimeError(f"H3 format correction returned an invalid {mode} prompt. {issue}")
    return prompt
