import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from support import h3_story_enhancer as h3
from support.h3_story_enhancer import H3_MODES, _search_templates, enhance_story
from support.instruct_completion import complete_instruct


class CompletionTests(unittest.TestCase):
    def test_cleans_explicit_and_prefilled_thinking(self):
        for content in (
            "<think>Reasoning\ncontinued</think>\nFinal",
            "Reasoning\ncontinued</think>\nFinal",
            "<THINK>Reasoning</THINK>\nFinal<think>later reasoning</think>",
            "Final<think>unfinished reasoning",
            "Final",
        ):
            with self.subTest(content=content):
                answer, _ = self.complete(content)
                self.assertEqual(answer, "Final")

    def test_length_limit_while_thinking_is_visible_in_logs(self):
        for content, prefill in (("<think>unfinished", False), ("unfinished", True)):
            with self.subTest(content=content), self.assertLogs("llama-cpp_vlm", "WARNING") as logs:
                self.assertEqual(self.complete(content, reason="length", prefill=prefill), ("", "length"))
                self.assertIn("finish_reason=length", logs.output[0])
                self.assertIn("max_tokens=16384", logs.output[0])

    def test_structured_reasoning_leaves_content_available(self):
        with self.assertLogs("llama-cpp_vlm", "WARNING"):
            result = self.complete("Partial answer", reason="length", prefill=True, reasoning_content="Some reasoning")
        self.assertEqual(result, ("Partial answer", "length"))

    def complete(self, content, reason="stop", prefill=False, **fields):
        llm = Mock()
        llm.n_ctx.return_value = 32768
        llm.create_chat_completion.return_value = {
            "choices": [{"message": {"content": content, **fields}, "finish_reason": reason}],
            "usage": {"prompt_tokens": 175, "completion_tokens": 16384},
        }
        result = complete_instruct(llm, [], 7, {"max_tokens": 16384}, stage="Instruct", prefilled_thinking=prefill)
        llm.create_chat_completion.assert_called_once_with(messages=[], seed=7, max_tokens=16384)
        return result


class H3Tests(unittest.TestCase):
    def test_auto_ref_keeps_media_and_original_brief_for_final_round(self):
        brief = "Two-turn dialogue with a silent reaction. Say exactly: 你先走。"
        picture = {"type": "image_url", "image_url": {"url": "data:image/png;base64,example"}}
        content = [{"type": "text", "text": brief}, picture, picture]
        final = "\n".join((
            "subject_definitions: …", "summary: [reference generation] …", "retention_analysis: …",
            "detailed_description: [Shot 1] <d>[Chinese] 你先走。</d>",
            "overall_soundscape: Rain.", "non_diegetic_music: N/A",
        ))
        selected = _search_templates(brief)[0]
        complete = Mock(side_effect=[('{"mode":"2ref2va", "template":1}', "stop"), ("Shot plan", "stop"), (final, "stop")])
        self.assertEqual(enhance_story("auto", content, [], "", complete, video_input=False), final)
        route, plan, writing = [call.args[0] for call in complete.call_args_list]
        self.assertIn("Attached images: 2", route[-1]["content"])
        self.assertIn(selected["mechanism"], plan[0]["content"])
        self.assertEqual(writing[-1]["content"][1:], [picture, picture])
        self.assertIn(brief, writing[-1]["content"][0]["text"])
        self.assertIn("Shot plan", writing[-1]["content"][0]["text"])

    def test_each_fixed_mode_uses_its_own_format(self):
        base = "integrated_multimodal_description: [Shot 1] Action.\noverall_soundscape: Rain.\nnon_diegetic_music: N/A"
        reference = ("subject_definitions: Source.\nsummary: [reference generation] Action.\n"
                     "retention_analysis: Source.\ndetailed_description: [Shot 1] Action.\n"
                     "overall_soundscape: Rain.\nnon_diegetic_music: N/A")
        alignments = {
            "i2va": "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.",
            "flf2va": "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.",
            "l2va": "How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 8.00-second mark of the target video.",
        }
        for mode in H3_MODES[2:]:
            with self.subTest(mode=mode):
                final = reference if mode.endswith("ref2va") else base
                if mode in alignments:
                    final = alignments[mode] + "\n\n" + final
                complete = Mock(side_effect=[('{"mode":"t2va","template":0}', "stop"), ("Plan", "stop"), (final, "stop")])
                self.assertEqual(enhance_story(mode, "Brief", [], "", complete, video_input=False), final)
                self.assertIn(f"for {mode}.", complete.call_args.args[0][0]["content"])

    def test_truncated_plan_does_not_trigger_writing(self):
        complete = Mock(side_effect=[('{"mode":"t2va","template":0}', "stop"), ("Partial plan", "length")])
        with self.assertRaisesRegex(RuntimeError, "story planning reached a generation limit"):
            enhance_story("auto", "Brief", [], "", complete, video_input=False)
        self.assertEqual(complete.call_count, 2)

    def test_invalid_reference_summary_gets_one_repair(self):
        draft = ("subject_definitions: Source.\nsummary: Action.\n"
                 "retention_analysis: Source.\ndetailed_description: [Shot 1] Action.\n"
                 "overall_soundscape: Rain.\nnon_diegetic_music: N/A")
        fixed = draft.replace("summary: Action.", "summary: [reference generation] Action.")
        complete = Mock(side_effect=[('{"mode":"1ref2va","template":0}', "stop"), ("Plan", "stop"),
                                     (draft, "stop"), (fixed, "stop")])
        self.assertEqual(enhance_story("auto", "Brief", [], "", complete, video_input=False), fixed)
        self.assertEqual(complete.call_args.args[1], "H3 format correction")
        self.assertIn("Start the summary body with the H3 task prefix", complete.call_args.args[0][0]["content"])


class T8CatalogTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="BK 模板 ")
        self.addCleanup(directory.cleanup)
        self.catalog = Path(directory.name) / "catalog" / "template-index.json"
        self.catalog.parent.mkdir()
        catalog_patch = patch.object(h3, "_T8_CATALOG", self.catalog)
        catalog_patch.start()
        self.addCleanup(catalog_patch.stop)
        h3._template_index.cache_clear()
        self.addCleanup(h3._template_index.cache_clear)

    def test_reads_live_h3_card_from_independent_catalog(self):
        card = {
            "models": ["MiniMax H3"], "titleEn": "Fresh fox template", "titleZh": "狐狸新範本",
            "tags": ["fox"], "mechanismEn": "The fox circles the lantern.", "mechanismZh": "狐狸繞著燈籠。",
            "requiredAnchorsZh": ["狐狸繞行"],
        }
        source = {"recommendationEntities": [
            {"templateId": "fresh-fox", "card": card},
            {"templateId": "seedance-only", "card": {**card, "models": ["Seedance 2.0"]}},
        ]}
        self.catalog.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
        results = _search_templates("狐狸新範本")
        self.assertEqual([card["id"] for card in results], ["fresh-fox"])
        self.assertEqual(results[0]["mechanism"], "The fox circles the lantern.")

    def test_absent_or_unusable_catalog_uses_bundled_cards(self):
        expected = [card["id"] for card in _search_templates("dialogue and silent reaction")]
        self.assertIn("stage-two-turn-pause-reaction", expected)
        self.catalog.write_text("{", encoding="utf-8")
        h3._template_index.cache_clear()
        with self.assertLogs("llama-cpp_vlm", "WARNING"):
            self.assertEqual([card["id"] for card in _search_templates("dialogue and silent reaction")], expected)


if __name__ == "__main__":
    unittest.main()
