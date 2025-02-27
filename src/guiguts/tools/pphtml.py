"""PPhtml tool."""

from dataclasses import dataclass
from html.parser import HTMLParser
import os.path
from tkinter import ttk
from typing import Any, Optional

from PIL import Image
import regex as re

from guiguts.checkers import CheckerDialog
from guiguts.file import the_file
from guiguts.maintext import maintext
from guiguts.preferences import preferences, PrefKey, PersistentBoolean
from guiguts.utilities import IndexRange, IndexRowCol


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

    def reset(self) -> None:
        """Reset PPhtml checker."""
        self.dialog.reset()
        self.image_files = []
        self.filedata = {}
        self.file_text = maintext().get_text()
        self.file_lines = self.file_text.split("\n")
        self.images_dir = os.path.join(os.path.dirname(the_file().filename), "images")

    def run(self) -> None:
        """Run PPhtml."""
        self.reset()
        self.image_tests()
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

    def heading_outline(self) -> None:
        """Output Document Heading Outline."""
        # Document Heading Outline
        parser = OutlineHTMLParser()
        parser.feed(self.file_text)
        self.add_section("Document Heading Outline")
        for line, pos in parser.outline:
            self.dialog.add_entry(line, pos)

    def output_subsection_errors(
        self, test_passed: Optional[bool], title: str, errors: list[str]
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
        for line in errors:
            self.dialog.add_entry(line)

    def add_section(self, text: str) -> None:
        """Add section heading to dialog."""
        self.dialog.add_header("", f"----- {text} -----")

    def add_subsection(self, text: str) -> None:
        """Add subsection heading to dialog."""
        self.dialog.add_header(f"--- {text} ---")


def pphtml() -> None:
    """Instantiate & run PPhtml checker."""
    PPhtmlChecker().run()
