import logging
import re


_logger = logging.getLogger("llama-cpp_vlm")
_think_tag = re.compile(r"<\s*(/?)\s*think\s*>", re.IGNORECASE)


def _answer_text(content, *, truncated, prefilled_thinking, structured_reasoning):
    text = (content or "").removeprefix(": ").strip()
    first_tag = _think_tag.search(text)
    if first_tag is None:
        # A Qwen template can supply the opening tag on the input side.
        if truncated and prefilled_thinking and not structured_reasoning:
            return ""
        return text

    parts = []
    start = first_tag.end() if first_tag.group(1) else 0
    depth = 0
    for tag in _think_tag.finditer(text, start):
        if not tag.group(1):
            if depth == 0:
                parts.append(text[start:tag.start()])
            depth += 1
        elif depth:
            depth -= 1
        else:
            parts.append(text[start:tag.start()])
        if depth == 0:
            start = tag.end()
    if depth == 0:
        parts.append(text[start:])
    return "".join(parts).strip()


def complete_instruct(llm, messages, seed, parameters, *, stage, prefilled_thinking):
    result = llm.create_chat_completion(messages=messages, seed=seed, **parameters)
    choice = result["choices"][0]
    message = choice["message"]
    reason = choice.get("finish_reason")
    answer = _answer_text(
        message.get("content"),
        truncated=reason == "length",
        prefilled_thinking=prefilled_thinking,
        structured_reasoning=any(message.get(key) is not None for key in ("reasoning", "reasoning_content")),
    )
    if reason == "length" or not answer:
        usage = result.get("usage") or {}
        _logger.warning(
            "%s: %s (finish_reason=%s, max_tokens=%s, n_ctx=%s, prompt_tokens=%s, completion_tokens=%s). %s",
            stage,
            "No answer after thinking cleanup" if not answer else "Answer reached a generation limit",
            reason,
            parameters.get("max_tokens", "backend default"),
            llm.n_ctx() if callable(getattr(llm, "n_ctx", None)) else "unknown",
            usage.get("prompt_tokens", "unknown"),
            usage.get("completion_tokens", "unknown"),
            "Check max_tokens and available context." if reason == "length" else "Check the model's chat template.",
        )
    return answer, reason
