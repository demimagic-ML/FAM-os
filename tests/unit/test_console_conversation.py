import json
import subprocess
import unittest
from pathlib import Path


class ConsoleConversationTests(unittest.TestCase):
    def test_result_reveal_is_bounded_progressive_and_completes_exactly(self) -> None:
        script = Path(__file__).parents[2] / (
            "src/fam_os/console/static/conversation.js"
        )
        program = r"""
const conversation = require(process.argv[1]);
const frames = [];
const element = {textContent: "pending"};
let completions = 0;
conversation.revealText(element, "abcdefghij", {
  requestFrame: callback => frames.push(callback),
  onComplete: () => completions += 1,
});
const duration = conversation.typingDuration(10);
frames.shift()(0);
const first = element.textContent;
frames.shift()(duration / 2);
const middle = element.textContent;
frames.shift()(duration);
console.log(JSON.stringify({
  duration,
  first,
  middle,
  final: element.textContent,
  completions,
}));
"""
        completed = subprocess.run(
            ("node", "-e", program, str(script)),
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(320, result["duration"])
        self.assertEqual("a", result["first"])
        self.assertEqual("abcde", result["middle"])
        self.assertEqual("abcdefghij", result["final"])
        self.assertEqual(1, result["completions"])

    def test_reduced_motion_reveals_immediately_and_scrolls_without_motion(self) -> None:
        script = Path(__file__).parents[2] / (
            "src/fam_os/console/static/conversation.js"
        )
        program = r"""
const conversation = require(process.argv[1]);
const element = {textContent: ""};
let queued = 0;
conversation.revealText(element, "Complete answer", {
  reducedMotion: true,
  requestFrame: () => queued += 1,
});
const calls = [];
const container = {
  scrollTop: 120,
  getBoundingClientRect: () => ({top: 80}),
  scrollTo: value => calls.push(value),
};
const message = {getBoundingClientRect: () => ({top: 260})};
conversation.scrollMessageStart(container, message, {
  reducedMotion: true,
  padding: 20,
});
console.log(JSON.stringify({text: element.textContent, queued, call: calls[0]}));
"""
        completed = subprocess.run(
            ("node", "-e", program, str(script)),
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual("Complete answer", result["text"])
        self.assertEqual(0, result["queued"])
        self.assertEqual({"top": 280, "behavior": "auto"}, result["call"])


if __name__ == "__main__":
    unittest.main()
