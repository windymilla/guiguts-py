"""Bookloupe check functionality"""

# Based on http://www.juiblex.co.uk/pgdp/bookloupe which
# was based on https://sourceforge.net/projects/gutcheck

from typing import Optional

import logging
import regex as re
import roman  # type: ignore[import-untyped]

from guiguts.checkers import CheckerDialog, CheckerEntry
from guiguts.maintext import maintext
from guiguts.misc_tools import tool_save
from guiguts.utilities import IndexRange, DiacriticRemover
from guiguts.widgets import ToolTip

logger = logging.getLogger(__package__)

_the_bookloupe_checker = None  # pylint: disable=invalid-name


class BookloupeCheckerDialog(CheckerDialog):
    """Minimal class to identify dialog type."""

    manual_page = "Tools_Menu#Bookloupe"


class BookloupeChecker:
    """Provides bookloupe check functionality."""

    def __init__(self) -> None:
        """Initialize BookloupeChecker class."""
        self.dictionary: dict[str, int] = {}
        self.dialog: Optional[BookloupeCheckerDialog] = None
        self.hebe_regex = re.compile(
            r'(?i)(\b(be could|be would|be is|was be|is be|to he)|",? be)\b'
        )
        self.hadbad_regex = re.compile(
            r"(?i)\b(the had|a had|they bad|she bad|he bad|you bad|i bad)\b"
        )
        self.hutbut_regex = re.compile(r"(?i)[;,] hut\b")

    def check_file(self) -> None:
        """Check for bookloupe errors in the currently loaded file."""

        # Create the checker dialog to show results
        self.dialog = BookloupeCheckerDialog.show_dialog(
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
        start_mark = BookloupeCheckerDialog.mark_from_rowcol(
            checker_entry.text_range.start
        )
        end_mark = BookloupeCheckerDialog.mark_from_rowcol(checker_entry.text_range.end)
        replacement_text = "FIXED"
        maintext().replace(start_mark, end_mark, replacement_text)

    def run_bookloupe(self) -> None:
        """Run the bookloupe checks and display the results in the dialog.

        Args:
            checkerdialog: Dialog to contain results.
        """
        next_step = 1
        para_first_step = 1
        paragraph = ""  # Store up paragraph for those checks that need whole para
        step_end = maintext().end().row
        while next_step <= step_end:
            step = next_step
            next_step += 1
            line = maintext().get(f"{step}.0", f"{step}.end")
            # If line is block markup or all asterisks/hyphens or page separator, skip
            if self.is_skippable_line(line):
                continue
            # Are we starting a new paragraph?
            if line and not paragraph:
                para_first_step = step
                paragraph = line
            # Deal with blank line
            if not line:
                # If paragraph has just ended, check quotes, etc. & ending punctuation
                if paragraph:
                    self.check_para(para_first_step, step - 1, paragraph)
                    paragraph = ""
                continue
            # Normal line
            self.check_odd_characters(step, line)
            self.check_hyphens(step, line)
            self.check_line_length(step, line)
            self.check_starting_punctuation(step, line)
            self.check_missing_para_break(step, line)
            self.check_jeebies(step, line)
            self.check_orphan_character(step, line)
            self.check_pling_scanno(step, line)
            self.check_extra_period(step, line)
            # Add line to paragraph
            paragraph += "\n" + line
        # End of file - check the final para
        if paragraph:
            self.check_para(para_first_step, step, paragraph)

    def check_para(self, para_start: int, para_end: int, para_text: str) -> None:
        """Check quotes & brackets are paired within given paragraph.
        Also that paragaph ends with suitable punctuation.

        For now, to be compatible with historic bookloupe, only checks
        straight quotes, and just does a simple count of open/close brackets.

        Args:
            para_start: First line number of paragraph.
            para_end: Last line number of paragraph.
            para_text: Text of paragraph.
        """
        assert self.dialog is not None
        start_index = f"{para_start}.0"
        end_index = maintext().index(f"{para_end}.end")
        para_range = IndexRange(start_index, end_index)
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
        # Does paragraph begin with a lowercase letter?
        if match := re.match(r"[ \P{IsAlnum}]*\p{Lowercase_Letter}", para_text):
            match_len = len(match[0])
            self.dialog.add_entry(
                "Paragraph starts with lower-case",
                IndexRange(
                    maintext().rowcol(f"{start_index}+{match_len - 1}c"),
                    maintext().rowcol(f"{start_index}+{match_len}c"),
                ),
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
        """Check for tabs, tildes, etc.

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
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
                    IndexRange(f"{step}.{idx}", f"{step}.{idx + 1}"),
                )

    def check_hyphens(self, step: int, line: str) -> None:
        """Check for leading/trailing hyphens, etc.

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        # Single (not double) hyphen at end of line
        if len(line) > 1 and line[-1] == "-" and line[-2] != "-":
            # If next line starts with hyphen, broken emdash?
            if maintext().get(f"{step + 1}.0") == "-":
                self.dialog.add_entry(
                    "Broken em-dash?",
                    IndexRange(maintext().rowcol(f"{step}.end-1c"), f"{step + 1}.1"),
                )
            # Otherwise query end of line hyphen
            else:
                self.dialog.add_entry(
                    "Hyphen at end of line?",
                    IndexRange(
                        maintext().rowcol(f"{step}.end-1c"),
                        maintext().rowcol(f"{step}.end"),
                    ),
                )
        # Spaced emdash (4 hyphens represents a word, so is allowed to be spaced)
        for match in re.finditer(" -- |(?<!--)-- | --(?!--)", line):
            self.add_match_entry(step, match, "Spaced em-dash?")
        # Spaced single hyphen/dash (don't report emdashes again)
        for match in re.finditer(" - |(?<!-)- | -(?!-)", line):
            self.add_match_entry(step, match, "Spaced dash?")

    def check_line_length(self, step: int, line: str) -> None:
        """Check for long or short lines.

        Args:
            step: Line number being checked.
            line: Text of line being checked.
            para_text: Text of paragraph up to this point,
        """
        assert self.dialog is not None
        longest_pg_line = 75
        shortest_pg_line = 55
        line_len = len(line)
        if line_len > longest_pg_line:
            self.dialog.add_entry(
                f"Long line {line_len}",
                IndexRange(f"{step}.{longest_pg_line}", f"{step}.{line_len + 1}"),
            )
            return
        # Short lines are not reported if they are not short!
        if line_len >= shortest_pg_line:
            return
        # Nor if they are indented (e.g. poetry)
        if line_len > 0 and line[0] == " ":
            return
        # Nor if they are the last line of a paragraph (allowed to be short)
        # Look backwards to find first non-skippable line & check if it's blank
        end_step = maintext().end().row
        for check_step in range(step + 1, end_step + 1):
            check_line = maintext().get(f"{check_step}.0", f"{check_step}.end")
            if not self.is_skippable_line(check_line):
                if len(check_line) == 0:
                    return
                break
        # Nor if the previous line was a short line (may be short-lined para, such as letter header)
        # Look backwards to find first non-skippable line & check its length
        for check_step in range(step - 1, 0, -1):
            check_line = maintext().get(f"{check_step}.0", f"{check_step}.end")
            if not self.is_skippable_line(check_line):
                if (
                    len(check_line) <= shortest_pg_line
                ):  # <= rather than < for backward compatibility
                    return
                break
        # None of the situations above happened, so it's a suspect short line
        self.dialog.add_entry(
            f"Short line {line_len}?",
            IndexRange(f"{step}.0", f"{step}.{line_len + 1}"),
        )

    def check_starting_punctuation(self, step: int, line: str) -> None:
        """Check for bad punctuation at start of line

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        if re.match(r"[?!,;:]|\.(?!( \. \.|\.\.))", line):
            self.dialog.add_entry(
                "Begins with punctuation?",
                IndexRange(f"{step}.0", f"{step}.1"),
            )

    def check_missing_para_break(self, step: int, line: str) -> None:
        """Check for missing paragraph break between quotes - straight doubles only.

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        if match := re.search(r'"  ?"', line):
            self.add_match_entry(
                step,
                match,
                "Query missing paragraph break?",
            )

    def check_jeebies(self, step: int, line: str) -> None:
        """Check for common he/be and other h/b errors.

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        for match in re.finditer(self.hebe_regex, line):
            self.add_match_entry(step, match, "Query he/be error?")
        for match in re.finditer(self.hadbad_regex, line):
            self.add_match_entry(step, match, "Query had/bad error?")
        for match in re.finditer(self.hutbut_regex, line):
            self.add_match_entry(step, match, "Query hut/but error?")

    def check_orphan_character(self, step: int, line: str) -> None:
        """Check for single character line, except (chapter/section/Roman?) numbers

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        if len(line) == 1 and line[0] not in "IVXL0123456789":
            self.dialog.add_entry(
                "Query single character line",
                IndexRange(f"{step}.0", f"{step}.1"),
            )

    def check_pling_scanno(self, step: int, line: str) -> None:
        """Check for ` I"`- often should be ` !`

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        for match in re.finditer(' I"', line):
            self.add_match_entry(step, match, "Query I=exclamation mark?")

    def check_extra_period(self, step: int, line: str) -> None:
        """Check for period not followed by capital letter.

        Args:
            step: Line number being checked.
            line: Text of line being checked.
        """
        assert self.dialog is not None
        for match in re.finditer(r"(\p{Letter}+)(\. \W*\p{Lowercase_Letter})", line):
            # Get the word before the period
            test_word = match[1]
            # Ignore single letter words or common abbreviations
            if len(test_word) == 1 or test_word.lower() in (
                "cent",
                "cents",
                "viz",
                "vol",
                "vols",
                "vid",
                "ed",
                "al",
                "etc",
                "op",
                "cit",
                "deg",
                "min",
                "chap",
                "oz",
                "mme",
                "mlle",
                "mssrs",
            ):
                continue
            # Ignore valid Roman numerals
            try:
                roman.fromRoman(test_word.upper())
                continue
            except roman.InvalidRomanNumeralError:
                pass
            # Only report if previous word contains vowels
            # (backward compatibility, except for addition of "y" as a vowel, for words like "try")
            if re.search("[aeiouy]", DiacriticRemover.remove_diacritics(test_word)):
                self.add_match_entry(step, match, "Extra period?", group=2)

    def add_match_entry(
        self, step: int, match: re.Match, message: str, group: int = 0
    ) -> None:
        """Add message about given match to dialog.

        Args:
            step: Line number being checked.
            match: Match for error on line.
            message: Text for error message.
            group: Optional captured group number
        """
        assert self.dialog is not None
        self.dialog.add_entry(
            message,
            IndexRange(f"{step}.{match.start(group)}", f"{step}.{match.end(group)}"),
        )

    def is_skippable_line(self, line: str) -> bool:
        """Return whether line should be skipped.

        Lines that contain DP block markup, page separators or thought breaks
        (`<tb>` or only asterisks/hyphens and spaces).

        Args:
            line: Text of line being checked.

        Returns:
            True if line should be skipped.
        """
        return bool(
            re.fullmatch(
                r"(/[\$xf\*plrci](\[\d+)?(\.\d+)?(,\d+)?]?|[\$xf\*plrci]/|<tb>|[* ]+|[- ]+|-----File:.+) *",
                line,
                flags=re.IGNORECASE,
            )
        )

    def remove_inline_markup(self, string: str) -> str:
        """Remove all types of DP inline markup from given string.

        Args:
            line: Text to be checked.

        Returns:
            String with DP inline markup  removed.
        """
        return re.sub(r"</?([ibfg]|sc)>", "", string)


def bookloupe_check() -> None:
    """Check for jeebies in the currently loaded file."""
    global _the_bookloupe_checker

    if not tool_save():
        return

    if _the_bookloupe_checker is None:
        _the_bookloupe_checker = BookloupeChecker()

    _the_bookloupe_checker.check_file()
