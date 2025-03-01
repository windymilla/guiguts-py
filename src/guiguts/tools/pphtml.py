"""PPhtml tool."""

from dataclasses import dataclass
from html.parser import HTMLParser
import os.path
from textwrap import wrap
from tkinter import ttk
from typing import Any, Optional

from PIL import Image
import regex as re

from guiguts.checkers import CheckerDialog, CheckerEntryType
from guiguts.file import the_file
from guiguts.maintext import maintext
from guiguts.preferences import preferences, PrefKey, PersistentBoolean
from guiguts.utilities import IndexRange, IndexRowCol, sing_plur


class OutlineHTMLParser(HTMLParser):
    """Parse HTML file to get document outline of h1-h6 elements"""

    h1_6_tags = ("h1", "h2", "h3", "h4", "h5", "h6")

    def __init__(self) -> None:
        """Initialize HTML outline parser."""
        super().__init__()
        self.outline: list[tuple[str, IndexRange]] = []
        self.tag = ""
        self.showh = False
        self.tag_start = IndexRowCol(0, 0)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle h1-h6 start tag."""
        if tag in self.h1_6_tags:
            self.tag = tag + ": "
            self.showh = True
            tag_index = self.getpos()
            self.tag_start = IndexRowCol(tag_index[0], tag_index[1])

    def handle_data(self, data: str) -> None:
        """Get contents of h1-h6 tag."""
        if self.showh:
            self.tag = self.tag + " " + data

    def handle_endtag(self, tag: str) -> None:
        """Handle h1-h6 end tag."""
        if tag in self.h1_6_tags:
            self.showh = False
            self.tag = self.tag.rstrip()
            self.tag = re.sub(r"\s+", " ", self.tag)
            match = re.match(r"h(\d)", self.tag)
            if match:
                indent = "  " * int(match.group(1))
                tag_index = self.getpos()
                self.outline.append(
                    (
                        "  " + indent + self.tag,
                        IndexRange(
                            self.tag_start, IndexRowCol(tag_index[0], tag_index[1] + 5)
                        ),
                    )
                )


class PPhtmlCheckerDialog(CheckerDialog):
    """Dialog to show PPhtml results."""

    manual_page = "HTML_Menu#PPhtml"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize PPhtml dialog."""
        super().__init__(
            "PPhtml Results",
            tooltip="\n".join(
                [
                    "Left click: Select & find error",
                    "Right click: Hide error",
                    "Shift Right click: Hide all matching errors",
                ]
            ),
            **kwargs,
        )
        ttk.Checkbutton(
            self.custom_frame,
            text="Verbose",
            variable=PersistentBoolean(PrefKey.PPHTML_VERBOSE),
            takefocus=False,
        ).grid(row=0, column=0, sticky="NSEW")


@dataclass
class PPhtmlFileData:
    """Class to hold info about an image file."""

    width: int
    height: int
    format: Optional[str]
    mode: str
    filesize: int


class PPhtmlChecker:
    """PPhtml checker"""

    def __init__(self) -> None:
        """Initialize PPhtml checker."""
        self.dialog = PPhtmlCheckerDialog.show_dialog(rerun_command=self.run)
        self.images_dir = ""
        self.image_files: list[str] = []  # list of files in images folder
        # dict of image file information (width, height, format, mode, filesize)
        self.filedata: dict[str, PPhtmlFileData] = {}
        self.file_text = ""  # Text of file
        self.file_lines: list[str] = []  # Text split into lines
        self.links: dict[str, list[IndexRange]] = {}
        self.targets: dict[str, list[IndexRange]] = {}

    def reset(self) -> None:
        """Reset PPhtml checker."""
        self.dialog.reset()
        self.images_dir = os.path.join(os.path.dirname(the_file().filename), "images")
        self.image_files = []
        self.filedata = {}
        self.file_text = maintext().get_text()
        self.file_lines = self.file_text.split("\n")
        self.links = {}
        self.targets = {}

    def run(self) -> None:
        """Run PPhtml."""
        self.reset()
        self.image_tests()
        self.link_tests()
        # self.ppvTests()
        # self.pgTests()
        # self.testCSS()
        # self.saveReport()
        self.heading_outline()

        self.dialog.display_entries()
        self.dialog.select_entry_by_index(0)

    def image_tests(self) -> None:
        """Various checks relating to image files."""

        # find filenames of all the images
        self.add_section("Image Checks")
        if not os.path.isdir(self.images_dir):
            self.dialog.add_entry("*** No images folder found ***")
            return
        self.image_files = [
            fn
            for fn in os.listdir(self.images_dir)
            if os.path.isfile(os.path.join(self.images_dir, fn))
        ]
        self.scan_images()
        self.all_images_used()
        self.all_targets_available()
        self.image_file_sizes()
        self.image_dimensions()
        if preferences.get(PrefKey.PPHTML_VERBOSE):
            self.image_summary()

    def scan_images(self) -> None:
        """Scan each image, getting size, checking filename, etc."""
        errors = []
        test_passed = True
        # Check filenames
        for filename in self.image_files:
            if " " in filename:
                errors.append(f"  filename '{filename}' contains spaces")
                test_passed = False
            if re.search(r"\p{Lu}", filename):
                errors.append(f"  filename '{filename}' not all lower case")
                test_passed = False

        # Make sure all are JPEG or PNG images
        for filename in self.image_files:
            filepath = os.path.join(self.images_dir, filename)
            try:
                with Image.open(filepath) as im:
                    fsize = os.path.getsize(filepath)
                    self.filedata[filename] = PPhtmlFileData(
                        im.width,
                        im.height,
                        im.format,
                        im.mode,
                        fsize,
                    )
            except IOError:
                errors.append(f"  file '{filename}' is not an image")
                test_passed = False
                continue
            if im.format not in ("JPEG", "PNG"):
                errors.append(f"  file '{filename}' is of type {im.format }")
                test_passed = False
        self.output_subsection_errors(
            test_passed, "Image folder consistency tests", errors
        )

    def all_images_used(self) -> None:
        """Verify all images in the images folder are used in the HTML."""
        errors = []
        test_passed = True
        count_images = 0
        for fn in self.filedata:
            count_images += 1
            if f"images/{fn}" not in self.file_text:
                errors.append(f"  Image '{fn}' not used in HTML")
                test_passed = False
        self.output_subsection_errors(
            test_passed, "Image folder files used in the HTML", errors
        )

    def all_targets_available(self) -> None:
        """Verify all target images in HTML are available in images folder."""
        errors = []
        test_passed = True
        for match in re.finditer(
            r"(?<=images/)[\p{Lowercase_Letter}-_\d]+\.(jpg|jpeg|png)", self.file_text
        ):
            filename = match[0]
            if filename not in self.filedata:
                errors.append(
                    f"  Image '{filename}' referenced in HTML not in images folder"
                )
                test_passed = False
        self.output_subsection_errors(
            test_passed, "Target images in HTML available in images folder", errors
        )

    def image_file_sizes(self) -> None:
        """Show image sizes, and warn/error about large images."""
        errors = []
        test_passed = True
        size_list = sorted(
            [(fname, data.filesize) for fname, data in self.filedata.items()],
            key=lambda tup: tup[1],
            reverse=True,
        )
        for fname, fsize in size_list:
            if fsize > 1024 * 1024:
                severity = "ERROR: "
                test_passed = False
            elif fsize > 256 * 1024:
                severity = "WARNING: "
            else:
                severity = ""
            errors.append(f"  {severity}{fname} ({int(fsize/1024)}K)")
        self.output_subsection_errors(test_passed, "Image File Sizes", errors)

    def image_dimensions(self) -> None:
        """Cover image width should be >=1600 px and height should be >= 2560 px.
        Other images must be <= 5000x5000."""
        errors: list[str] = []
        test_passed = True
        for fname, filedata in self.filedata.items():
            wd = filedata.width
            ht = filedata.height
            if fname == "cover.jpg" and (wd < 1600 or ht < 2560):
                errors.insert(
                    0,
                    f"  WARNING: {fname} too small (actual: {wd}x{ht}; recommended >= 1600x2560)",
                )
                test_passed = False
            elif wd > 5000 or ht > 5000:
                errors.insert(
                    0,
                    f"  WARNING: {fname} too large (actual: {wd}x{ht}; recommended <= 5000x5000)",
                )
                test_passed = False

        self.output_subsection_errors(test_passed, "Image Dimensions Check", errors)

    def image_summary(self) -> None:
        """Show information about image (verbose mode only)."""
        type_desc = {
            "1": "(1-bit pixels, black and white, stored with one pixel per byte)",
            "L": "(8-bit pixels, black and white)",
            "P": "(8-bit pixels, mapped to any other mode using a color palette)",
            "RGB": "(3x8-bit pixels, true color)",
            "RGBA": "(4x8-bit pixels, true color with transparency mask)",
            "CMYK": "(4x8-bit pixels, color separation)",
            "YCbCr": "(3x8-bit pixels, color video format)",
            "LAB": "(3x8-bit pixels, the L*a*b color space)",
            "HSV": "(3x8-bit pixels, Hue, Saturation, Value color space)",
            "I": "(32-bit signed integer pixels)",
            "F": "(32-bit floating point pixels)",
        }

        messages = []
        for fname, filedata in self.filedata.items():
            mode_desc = type_desc.get(filedata.mode, filedata.mode)
            messages.append(
                f"  {fname}, {filedata.width}x{filedata.height}, {filedata.format} {mode_desc}"
            )
        self.output_subsection_errors(None, "Image Summary", messages)

    def link_tests(self) -> None:
        """Consolidated link tests."""
        self.add_section("Link Tests")

        self.external_links()
        self.link_to_cover()
        self.find_links()
        self.find_targets()
        self.link_counts()
        self.do_resolve()

    def external_links(self) -> None:
        """Report and external href links."""
        errors: list[tuple[str, Optional[IndexRange]]] = []
        test_passed = True
        count_links = 0
        for line_num, line in enumerate(self.file_lines):
            if match := re.search(r"https?://[^'\"\) ]*", line):
                test_passed = False
                if count_links <= 10:
                    start = IndexRowCol(line_num + 1, match.span()[0])
                    end = IndexRowCol(line_num + 1, match.span()[1])
                    errors.append(
                        (f"External link: {match[0]}", IndexRange(start, end))
                    )
                if not preferences.get(PrefKey.PPHTML_VERBOSE):
                    count_links += 1
        self.output_subsection_errors(test_passed, "External Links Check", errors)
        if count_links > 10:
            self.dialog.new_section()
            self.dialog.add_entry(
                "  (more external links not reported)",
                entry_type=CheckerEntryType.FOOTER,
            )

    def link_to_cover(self) -> None:
        """Check that an epub cover has been provided:
        1. id of "coverpage" on an image
        2. `link rel="icon"` in header
        3. file named "cover.jpg" or "cover.png" in images folder
        """
        title = "Link to cover image for epub"
        test_passed = False
        if re.search("id *= *['\"]coverpage['\"]", self.file_text):
            test_passed = True
            title += " (using id='coverpage' on image)"
        elif re.search("rel *= *['\"]icon['\"]", self.file_text):
            test_passed = True
            title += " (using link rel='icon')"
        elif "cover.jpg" in self.filedata:
            test_passed = True
            title += " (found cover.jpg in images folder)"
        elif "cover.png" in self.filedata:
            test_passed = True
            title += " (found cover.png in images folder)"
        self.output_subsection_errors(test_passed, title, [])

    def find_links(self) -> None:
        """Build dictionary of IndexRanges where internal link occurs, keyed on target name."""
        link_count = 0
        for line_num, line in enumerate(self.file_lines):
            for match in re.finditer(r"href\s*=\s*[\"']#(.*?)[\"']", line):
                link_count += 1
                tgt = match[1]
                idx_range = IndexRange(
                    IndexRowCol(line_num + 1, match.start()),
                    IndexRowCol(line_num + 1, match.end()),
                )
                if tgt in self.links:
                    self.links[tgt].append(idx_range)
                else:
                    self.links[tgt] = [idx_range]
        self.output_subsection_errors(
            None,
            f"File has {link_count} internal links to {len(self.links)} expected targets",
            [],
        )

    def find_targets(self) -> None:
        """Build dictionary of IndexRanges where targets occur, keyed on target name.
        Should be only one for each id."""
        id_count = 0
        for line_num, line in enumerate(self.file_lines):
            if "<meta" in line:
                continue
            for match in re.finditer(r"id\s*=\s*[\"'](.*?)[\"']", line):
                id_count += 1
                tgt = match[1]
                idx_range = IndexRange(
                    IndexRowCol(line_num + 1, match.start()),
                    IndexRowCol(line_num + 1, match.end()),
                )
                if tgt in self.targets:
                    self.targets[tgt].append(idx_range)
                else:
                    self.targets[tgt] = [idx_range]

        errors: list[tuple[str, Optional[IndexRange]]] = []
        test_passed = True
        for tgt, idx_ranges in self.targets.items():
            if len(idx_ranges) > 1:
                test_passed = False
                for idx_range in idx_ranges:
                    errors.append((f"Duplicate id: {tgt}", idx_range))
        self.output_subsection_errors(
            test_passed,
            f"Duplicate ID Check (file has {len(self.targets)} unique IDs)",
            errors,
        )

    def link_counts(self) -> None:
        """Check for multiple links to the same ID, and report number of image links."""
        errors: list[tuple[str, Optional[IndexRange]]] = []
        test_passed = True
        num_reused = 0
        for tgt, idx_ranges in self.links.items():
            if len(idx_ranges) > 1:
                test_passed = False
                num_reused += 1
                for idx_range in idx_ranges:
                    errors.append((f"WARNING: Multiple links to id {tgt}", idx_range))
        if num_reused <= 5:
            self.output_subsection_errors(
                test_passed,
                "Check for IDs targeted by multiple links",
                errors,
            )
        else:
            self.output_subsection_errors(
                None,
                f"Not reporting {num_reused} IDs linked to more than once (file may have an index)",
                [],
            )

        im_count = 0
        inc_cover = ""
        for line in self.file_lines:
            for match in re.finditer(r'href=["\']images/(.*?)["\']', line):
                if match[1].startswith("cover."):
                    inc_cover = f" (including {match[1]})"
                im_count += 1
        if im_count > 0:
            self.output_subsection_errors(
                None,
                f"File has {sing_plur(im_count, 'link')} to images{inc_cover}",
                [],
            )

    def do_resolve(self) -> None:
        """Every link must go to one link target that exists (or flag missing link target).
        Every target should come from one or more links (or flag unused target)
        """
        errors: list[tuple[str, Optional[IndexRange]]] = []
        test_passed = True
        for alink, idx_ranges in self.links.items():
            if alink not in self.targets:
                test_passed = False
                for idx_range in idx_ranges:
                    errors.append((f"  Target {alink} not found", idx_range))
        self.output_subsection_errors(
            test_passed, "Check links point to valid targets", errors
        )

        reported = 0
        report_limit = 20
        untargeted = []
        for atarget in self.targets:
            if atarget not in self.links:
                reported += 1
                if reported > report_limit:
                    break
                untargeted.append(atarget)
        join_string = ", ".join(untargeted)
        wrapped_lines = wrap(
            join_string, width=60, initial_indent="  ", subsequent_indent="  "
        )
        if reported > report_limit:
            wrapped_lines[-1] += " ... more not reported"
        self.output_subsection_errors(
            reported == 0, "Check for unreferenced targets", wrapped_lines
        )

    def heading_outline(self) -> None:
        """Output Document Heading Outline."""
        # Document Heading Outline
        parser = OutlineHTMLParser()
        parser.feed(self.file_text)
        self.add_section("Document Heading Outline")
        for line, pos in parser.outline:
            self.dialog.add_entry(line, pos)

    def output_subsection_errors(
        self,
        test_passed: Optional[bool],
        title: str,
        errors: list[str] | list[tuple[str, Optional[IndexRange]]],
    ) -> None:
        """Output collected errors underneath subsection title.

        Args:
            test_passed: Whether the test passed, i.e. no errors. None for info only
            title: Title for this check.
            errors: List of errors to be output.
        """
        if test_passed is None:
            pass_string = "[info]"
        else:
            pass_string = "[pass]" if test_passed else "*FAIL*"
        self.add_subsection(f"{pass_string} {title}")
        for error in errors:
            if isinstance(error, str):
                self.dialog.add_entry(error)
            else:
                self.dialog.add_entry(error[0], error[1])

    def add_section(self, text: str) -> None:
        """Add section heading to dialog."""
        self.dialog.add_header("", f"----- {text} -----")

    def add_subsection(self, text: str) -> None:
        """Add subsection heading to dialog."""
        self.dialog.add_header(f"--- {text} ---")


def pphtml() -> None:
    """Instantiate & run PPhtml checker."""
    PPhtmlChecker().run()
