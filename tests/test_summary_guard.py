"""Checks that model notes never become a published summary.

Run from the Snewzy folder:  python3 -m unittest tests.test_summary_guard -v
"""
import unittest

from news_hub.modules.summarizer import looks_like_model_notes, parse_response, strip_thinking

LEAKED = ("Hmm, the user wants me to summarize a news article about Jensen Huang's return at Nvidia. "
          "They've specified that today is November 25, 2026, but I shouldn't comment on the date. "
          "The priority is critical importance, so I need to be thorough.")


class ModelNotes(unittest.TestCase):
    def test_real_leak_is_caught(self):
        self.assertTrue(looks_like_model_notes(LEAKED))

    def test_other_note_styles_are_caught(self):
        for t in ["Okay, let me summarize this article.", "Let me start by reading the article.",
                  "I need to keep it to four sentences.", "The user asked for bullet points.",
                  "Following the instructions, here is a summary of the article."]:
            self.assertTrue(looks_like_model_notes(t), t)

    def test_normal_news_is_not_flagged(self):
        for t in ["The update changes the user interface and adds a dark mode.",
                  "A federal task force said the top priority is restoring power.",
                  "Researchers released a benchmark of 137,745 clips from 15,014 source pairs.",
                  "The CEO said he will step down in March.",
                  "Officials said the instructions for voters were mailed last week."]:
            self.assertFalse(looks_like_model_notes(t), t)


class ParseResponse(unittest.TestCase):
    def test_good_reply(self):
        s, b = parse_response("SUMMARY: Nvidia reported record revenue. Shares rose.\n\nBULLET POINTS:\n- Record revenue\n- Shares up")
        self.assertEqual(s, "Nvidia reported record revenue. Shares rose.")
        self.assertIn("- Record revenue", b)

    def test_reply_without_format_is_rejected(self):
        self.assertEqual(parse_response(LEAKED), (None, None))

    def test_notes_inside_summary_are_rejected(self):
        self.assertEqual(parse_response("SUMMARY: " + LEAKED + "\nBULLET POINTS:\n- x"), (None, None))

    def test_empty_reply_is_rejected(self):
        self.assertEqual(parse_response(""), (None, None))


class StripThinking(unittest.TestCase):
    def test_paired_tags(self):
        self.assertEqual(strip_thinking("<think>notes</think>SUMMARY: ok."), "SUMMARY: ok.")

    def test_lone_closing_tag(self):
        self.assertEqual(strip_thinking("Hmm, the user wants...</think>\nSUMMARY: ok."), "SUMMARY: ok.")


if __name__ == "__main__":
    unittest.main()


class RetryThenSkip(unittest.TestCase):
    """summarize_article with the model and database replaced by stand-ins."""

    def run_with(self, replies):
        from news_hub.modules import summarizer as S
        calls = {"saved": None, "status": None, "asked": 0}
        it = iter(replies)
        orig = (S.call_ollama, S.update_article_summary, S.mark_article_status)
        def fake_call(*a, **k):
            calls["asked"] += 1
            return next(it)
        S.call_ollama = fake_call
        S.update_article_summary = lambda i, s, b: calls.__setitem__("saved", s)
        S.mark_article_status = lambda i, st: calls.__setitem__("status", st)
        try:
            ok = S.summarize_article((7, "Title", "src", "url", "date", "content", None, None, 1), "m")
        finally:
            S.call_ollama, S.update_article_summary, S.mark_article_status = orig
        return ok, calls

    def test_second_try_succeeds(self):
        ok, c = self.run_with([LEAKED, "SUMMARY: A real summary.\nBULLET POINTS:\n- one"])
        self.assertTrue(ok); self.assertEqual(c["saved"], "A real summary."); self.assertEqual(c["asked"], 2)

    def test_two_bad_replies_mark_it_and_save_nothing(self):
        ok, c = self.run_with([LEAKED, LEAKED])
        self.assertFalse(ok); self.assertIsNone(c["saved"]); self.assertEqual(c["status"], "unsummarized")

    def test_ollama_down_leaves_it_pending(self):
        ok, c = self.run_with([None])
        self.assertFalse(ok); self.assertIsNone(c["status"]); self.assertEqual(c["asked"], 1)
