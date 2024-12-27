"""Bookloupe check functionality"""

# Based on http://www.juiblex.co.uk/pgdp/bookloupe which
# was based on https://sourceforge.net/projects/gutcheck

from typing import Optional

import logging
import regex as re

from guiguts.checkers import CheckerDialog, CheckerEntry
from guiguts.maintext import maintext
from guiguts.misc_tools import tool_save
from guiguts.utilities import IndexRange
from guiguts.widgets import ToolTip

logger = logging.getLogger(__package__)

_the_bookloupe_checker = None  # pylint: disable=invalid-name


class BookloupeChecker:
    """Provides bookloupe check functionality."""

    def __init__(self) -> None:
        """Initialize BookloupeChecker class."""
        self.dictionary: dict[str, int] = {}
        self.dialog: Optional[CheckerDialog] = None

    def check_file(self) -> None:
        """Check for bookloupe errors in the currently loaded file."""

        # Create the checker dialog to show results
        self.dialog = CheckerDialog.show_dialog(
            "Bookloupe Results",
            rerun_command=bookloupe_check,
            process_command=self.process_bookloupe,
        )
        ToolTip(
            self.dialog.text,
            "\n".join(
                [
                    "Left click: FIX THIS",
                    "Right click: AND THIS",
                ]
            ),
            use_pointer_pos=True,
        )
        self.dialog.reset()
        self.run_bookloupe()
        self.dialog.display_entries()

    def process_bookloupe(self, checker_entry: CheckerEntry) -> None:
        """Process the Bookloupe query."""
        if checker_entry.text_range is None:
            return
        start_mark = CheckerDialog.mark_from_rowcol(checker_entry.text_range.start)
        end_mark = CheckerDialog.mark_from_rowcol(checker_entry.text_range.end)
        replacement_text = "FIXED"
        maintext().replace(start_mark, end_mark, replacement_text)

    def run_bookloupe(self) -> None:
        """Run the bookloupe checks and display the results in the dialog.

        Args:
            checkerdialog: Dialog to contain results.
        """
        next_step = 1
        para_first_step = 1
        in_para = False
        step_end = maintext().end().row
        while next_step <= step_end:
            step = next_step
            next_step += 1
            line = maintext().get(f"{step}.0", f"{step}.end")
            # If line is block markup or all asterisks or all hyphens, replace with blank line
            line = self.remove_block_markup(line)
            # Are we starting a new paragraph?
            if line and not in_para:
                para_first_step = step
                in_para = True
            # Deal with blank line
            if not line:
                # If paragraph has just ended, check quotes, etc. & ending punctuation
                if in_para:
                    self.check_para(para_first_step, step - 1)
                    in_para = False
                continue
            # Normal line
            self.check_odd_characters(step, line)
        # End of file - check the final para
        if in_para:
            self.check_para(para_first_step, step)

    def check_para(self, para_start: int, para_end: int) -> None:
        """Check quotes & brackets are paired within given paragraph.
        Also that paragaph ends with suitable punctuation.

        For now, to be compatible with historic bookloupe, only checks
        straight quotes, and just does a simple count of open/close brackets.

        Args:
            para_start: First line number of paragraph.
            para_end: Last line number of paragraph.
        """
        assert self.dialog is not None
        start_index = f"{para_start}.0"
        end_index = maintext().index(f"{para_end}.end")
        para_range = IndexRange(start_index, end_index)
        para_text = maintext().get(start_index, end_index)
        # Straight double quotes - an odd number means a potential error unless
        # the next paragraph starts with a double quote
        if para_text.count('"') % 2 and maintext().get(f"{para_end}.0+2l") != '"':
            self.dialog.add_entry(
                "Mismatched double quotes",
                para_range,
            )
        # Straight single quotes - add the open quotes, subtract the close quotes,
        # try to allow for apostrophes, so should get zero. Allow +1 if the next
        # paragraph starts with a single quote
        open_quote_count = len(re.findall(r"(?<!\p{Letter})'(?=\p{Letter})", para_text))
        open_quote_count -= len(re.findall(r"'[Tt]is\b", para_text))  # Common exception
        close_quote_count = len(
            re.findall(r"(?<=[\p{Letter}\p{Punctuation}])'(?!\p{Letter})", para_text)
        )
        if open_quote_count != close_quote_count and (
            open_quote_count != close_quote_count + 1
            or maintext().get(f"{para_end}.0+2l") != "'"
        ):
            self.dialog.add_entry(
                "Mismatched single quotes?",
                para_range,
            )
        # Underscores - should be an even number
        if para_text.count("_") % 2:
            self.dialog.add_entry(
                "Mismatched underscores?",
                para_range,
            )
        # Brackets - should be equal number of open & close
        if para_text.count("(") != para_text.count(")"):
            self.dialog.add_entry(
                "Mismatched round brackets?",
                para_range,
            )
        if para_text.count("[") != para_text.count("]"):
            self.dialog.add_entry(
                "Mismatched square brackets?",
                para_range,
            )
        if para_text.count("{") != para_text.count("}"):
            self.dialog.add_entry(
                "Mismatched curly brackets?",
                para_range,
            )
        # Does paragraph end with suitable punctuation
        # Ignore single line paragraphs & those without any lowercase letters,
        # in order to avoid false positives from chapter headings, etc.
        if para_start == para_end or not re.search(r"\p{Lowercase_Letter}", para_text):
            return
        # Ignoring any character that is not alphanumeric or sentence-ending punctuation,
        # last character (ignoring inline markup) must be sentence-ending punctuation.
        se_punc = "-—.:!?"
        last_line = para_text.splitlines()[-1]
        last_line = re.sub(
            rf"[^{se_punc}()[]{{}}\p{{Letter}}\p{{Number}}", "", last_line
        )
        last_line = self.remove_inline_markup(last_line)
        if last_line[-1] not in se_punc:
            self.dialog.add_entry(
                "No punctuation at para end?",
                IndexRange(maintext().rowcol(f"{end_index}-1c"), end_index),
            )

    def check_odd_characters(self, step: int, line: str) -> None:
        """Check for tabs, tildes, etc."""
        assert self.dialog is not None
        odd_char_names = {
            "\t": "Tab character?",
            "~": "Tilde character?",
            "^": "Carat character?",
            "/": "Forward slash?",
            "*": "Asterisk",
        }
        for idx, ltr in enumerate(line):
            if ltr in odd_char_names:
                self.dialog.add_entry(
                    odd_char_names[ltr],
                    IndexRange(f"{step}.{idx}", f"{step}.{idx+1}"),
                )

    def remove_block_markup(self, string: str) -> str:
        """Clear lines that contain all types of DP block markup or thought breaks.

        Thought breaks are `<tb>` or consist only of asterisks or hyphens (and spaces).
        """
        return re.sub(
            r"^(/([\$xf\*plrci])(\[\d+)?(\.\d+)?(,\d+)?]?|[\$xf\*plrci]/|<tb>|[* ]+|[- ]+) *$",
            "",
            string,
            flags=re.IGNORECASE,
        )

    def remove_inline_markup(self, string: str) -> str:
        """Remove all types of DP inline markup from given string."""
        return re.sub(r"</?([ibfg]|sc)>", "", string)


def bookloupe_check() -> None:
    """Check for jeebies in the currently loaded file."""
    global _the_bookloupe_checker

    if not tool_save():
        return

    if _the_bookloupe_checker is None:
        _the_bookloupe_checker = BookloupeChecker()

    _the_bookloupe_checker.check_file()
