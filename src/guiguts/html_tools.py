"""Tools relating to HTML."""

import logging
import os.path
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional

from PIL import Image, ImageTk, UnidentifiedImageError
import regex as re

from guiguts.file import the_file
from guiguts.maintext import maintext
from guiguts.utilities import IndexRange, sound_bell, DiacriticRemover
from guiguts.widgets import ToplevelDialog

logger = logging.getLogger(__package__)

IMAGE_THUMB_SIZE = 200
RETURN_ARROW = "⏎"


class HTMLImageDialog(ToplevelDialog):
    """Dialog for inserting image markup into HTML."""

    manual_page = "HTML_Menu#Add_Illustrations"

    def __init__(self) -> None:
        """Initialize HTML Image dialog."""
        super().__init__(
            "HTML Images",
            resize_x=False,
            resize_y=False,
        )

        self.image: Optional[Image.Image] = None
        self.imagetk: Optional[ImageTk.PhotoImage] = None
        self.width = 0
        self.height = 0
        self.illo_range: Optional[IndexRange] = None

        # File
        file_frame = ttk.LabelFrame(self.top_frame, text="File", padding=2)
        file_frame.grid(row=0, column=0, sticky="NSEW")
        file_frame.columnconfigure(0, weight=1)
        file_name_frame = ttk.Frame(file_frame)
        file_name_frame.grid(row=0, column=0)
        file_name_frame.columnconfigure(0, weight=1)
        self.filename_textvariable = tk.StringVar(self, "")
        self.fn_entry = ttk.Entry(
            file_name_frame,
            textvariable=self.filename_textvariable,
            width=30,
        )
        self.fn_entry.grid(row=0, column=0, sticky="EW", padx=(0, 2))
        ttk.Button(
            file_name_frame,
            text="Browse...",
            command=self.choose_file,
            takefocus=False,
        ).grid(row=0, column=1, sticky="NSEW")

        # Buttons to see prev/next file
        file_btn_frame = ttk.Frame(file_frame)
        file_btn_frame.grid(row=1, column=0)
        ttk.Button(
            file_btn_frame,
            text="Prev File",
            command=lambda: self.next_file(reverse=True),
            takefocus=False,
        ).grid(row=0, column=0, padx=2)
        ttk.Button(
            file_btn_frame,
            text="Next File",
            command=lambda: self.next_file,
            takefocus=False,
        ).grid(row=0, column=1, padx=2)

        # Label to display thumbnail of image - allocate a
        # square space the same width as the filename frame
        file_name_frame.update_idletasks()
        frame_width = file_name_frame.winfo_width()
        thumbnail_frame = ttk.LabelFrame(self.top_frame, text="Thumbnail")
        thumbnail_frame.grid(row=1, column=0, sticky="NSEW")
        thumbnail_frame.columnconfigure(0, minsize=frame_width, weight=1)
        thumbnail_frame.rowconfigure(0, minsize=frame_width, weight=1)
        self.thumbnail = ttk.Label(thumbnail_frame, justify=tk.CENTER)
        self.thumbnail.grid(row=0, column=0)
        self.thumbsize = frame_width - 10

        # Caption text
        caption_frame = ttk.LabelFrame(self.top_frame, text="Caption text", padding=2)
        caption_frame.grid(row=2, column=0, sticky="NSEW")
        caption_frame.columnconfigure(0, weight=1)
        self.caption_textvariable = tk.StringVar(self, "")
        ttk.Entry(
            caption_frame,
            textvariable=self.caption_textvariable,
        ).grid(row=0, column=0, sticky="NSEW")

        # Alt text
        alt_frame = ttk.LabelFrame(self.top_frame, text="Alt text", padding=2)
        alt_frame.grid(row=3, column=0, sticky="NSEW")
        alt_frame.columnconfigure(0, weight=1)
        self.alt_textvariable = tk.StringVar(self, "")
        ttk.Entry(
            alt_frame,
            textvariable=self.alt_textvariable,
        ).grid(row=0, column=0, sticky="NSEW")

        # Geometry
        geom_frame = ttk.LabelFrame(self.top_frame, padding=2, text="Geometry")
        geom_frame.grid(row=5, column=0, pady=(5, 0), sticky="NSEW")
        geom_frame.columnconfigure(0, weight=1)
        width_height_frame = ttk.Frame(geom_frame)
        width_height_frame.grid(row=0, column=0)
        width_height_frame.columnconfigure(0, weight=1)
        ttk.Label(width_height_frame, text="Width").grid(row=0, column=0, padx=4)
        self.width_textvariable = tk.StringVar(self, "")
        ttk.Entry(
            width_height_frame, textvariable=self.width_textvariable, width=5
        ).grid(row=0, column=1, sticky="NSEW", padx=(4, 10))
        ttk.Label(width_height_frame, text="Height").grid(row=0, column=2, padx=(10, 4))
        self.height_textvariable = tk.StringVar(self, "")
        ttk.Entry(
            width_height_frame, textvariable=self.height_textvariable, width=5
        ).grid(row=0, column=3, sticky="NSEW", padx=4)
        self.unit_textvariable = tk.StringVar(self, "%")
        unit_frame = ttk.Frame(geom_frame)
        unit_frame.grid(row=1, column=0, pady=5)
        ttk.Radiobutton(
            unit_frame, text="%", variable=self.unit_textvariable, value="%"
        ).grid(row=0, column=4, sticky="NSEW", padx=10)
        ttk.Radiobutton(
            unit_frame, text="em", variable=self.unit_textvariable, value="em"
        ).grid(row=0, column=5, sticky="NSEW", padx=10)
        ttk.Radiobutton(
            unit_frame, text="px", variable=self.unit_textvariable, value="px"
        ).grid(row=0, column=6, sticky="NSEW", padx=10)

        # Buttons to Find illos and Convert to HTML
        btn_frame = ttk.Frame(self.top_frame, padding=2)
        btn_frame.grid(row=6, column=0, pady=(5, 0))
        ttk.Button(
            btn_frame,
            text="Convert to HTML",
            command=self.convert_to_html,
            takefocus=False,
            width=18,
        ).grid(row=0, column=0, sticky="NSEW", padx=2)
        ttk.Button(
            btn_frame,
            text="Find [Illustration]",
            command=self.find_illo_markup,
            takefocus=False,
            width=18,
        ).grid(row=0, column=1, sticky="NSEW", padx=2)

        self.find_illo_markup()

    def load_file(self, file_name: str) -> None:
        """Load given image file."""
        assert file_name
        file_name = os.path.normpath(file_name)
        if not os.path.isfile(file_name):
            logger.error(f"Unsuitable image file: {file_name}")
            self.clear_image()
            return

        # Display filename and load image file
        rel_file_name = os.path.relpath(
            file_name, start=os.path.dirname(the_file().filename)
        )
        self.filename_textvariable.set(rel_file_name)
        self.fn_entry.xview_moveto(1.0)
        if self.image is not None:
            del self.image
        try:
            self.image = Image.open(file_name).convert("RGB")
        except UnidentifiedImageError:
            self.image = None
            logger.error(f"Unable to identify image file: {file_name}")
            return
        width, height = self.image.size
        if width <= 0 or height <= 0:
            logger.error(f"Image file has illegal width/height: {file_name}")
            return
        # Resize image to fit thumbnail label
        scale = min(self.thumbsize / width, self.thumbsize / height, 1.0)
        width = int(width * scale)
        height = int(height * scale)
        image = self.image.resize(
            size=(width, height), resample=Image.Resampling.LANCZOS
        )
        if self.imagetk:
            del self.imagetk
        self.imagetk = ImageTk.PhotoImage(image)
        del image
        self.thumbnail.config(image=self.imagetk)
        self.lift()

    def choose_file(self) -> None:
        """Allow user to choose image file."""
        if file_name := filedialog.askopenfilename(
            filetypes=(
                ("Image files", "*.jpg *.png *.gif"),
                ("All files", "*.*"),
            ),
            title="Select Image File",
            parent=self,
        ):
            self.load_file(file_name)

    def next_file(self, reverse: bool = False) -> None:
        """Load the next file alphabetically.

        Args:
            reverse: True to load previous file instead.
        """
        # If no current file, can't get "next", so make user choose one
        current_fn = self.filename_textvariable.get()
        if not current_fn:
            self.choose_file()
            return
        current_fn = os.path.join(os.path.dirname(the_file().filename), current_fn)
        # Check current directory is valid
        current_dir = os.path.dirname(current_fn)
        if not os.path.isdir(current_dir):
            logger.error(f"Image directory invalid: {current_dir}")
            return
        current_basename = os.path.basename(current_fn)
        found = False
        for fn in sorted(os.listdir(current_dir), reverse=reverse):
            # Skip non-image files by checking extension
            if os.path.splitext(fn)[1] not in (".jpg", ".gif", ".png"):
                continue
            # If found on previous time through loop, this is the file we want
            if found:
                self.load_file(os.path.join(current_dir, fn))
                return
            if fn == current_basename:
                found = True
        # Reached end of dir listing without finding next file
        sound_bell()

    def find_illo_markup(self) -> None:
        """Find first unconverted illo markup in file and
        advance to the next file."""
        self.illo_range = None
        # Find and go to start of first unconverted illo markup
        illo_match_start = maintext().find_match(
            r"(<p>)?\[Illustration",
            IndexRange(maintext().start(), maintext().end()),
            regexp=True,
        )
        if illo_match_start is None:
            sound_bell()
            return
        maintext().set_insert_index(illo_match_start.rowcol, focus=False)
        # Find end of markup and spotlight it
        illo_match_end = maintext().find_match(
            r"](</p>)?",
            IndexRange(illo_match_start.rowcol, maintext().end()),
            regexp=True,
        )
        if illo_match_end is None:
            logger.error("Unclosed [Illustration markup")
            return
        self.illo_range = IndexRange(
            illo_match_start.rowcol,
            maintext().rowcol(
                f"{illo_match_end.rowcol.index()}+{illo_match_end.count}c"
            ),
        )
        maintext().spotlight_range(self.illo_range)
        # Display caption in dialog and add <p> markup if none
        caption = maintext().get(
            self.illo_range.start.index(), self.illo_range.end.index()
        )
        caption = re.sub(r"^\[Illustration:? ?", "", caption)
        caption = re.sub(r"\]$", "", caption)
        caption = re.sub("^(?!<p)", "<p>", caption)
        caption = re.sub("(?<!</p>)$", "</p>", caption)
        caption = re.sub("\n\n", "</p>\n<p>", caption)
        caption = re.sub("\n", RETURN_ARROW, caption)
        self.caption_textvariable.set(caption)
        # Clear alt text, ready for user to type in required string
        self.alt_textvariable.set("")
        self.next_file()
        self.lift()

    def convert_to_html(self) -> None:
        """Convert selected [Illustration...] markup to HTML."""
        filename = self.filename_textvariable.get()
        if self.illo_range is None or not filename:
            sound_bell()
            return
        # Get caption & add some space to prettify HTML
        caption = self.caption_textvariable.get()
        caption = re.sub("^<p", "    <p", caption)
        # caption = re.sub(f"{RETURN_ARROW}<p", "\n    <p", caption)
        caption = re.sub(RETURN_ARROW, "\n    ", caption)
        if caption:
            caption = f'  <figcaption class="caption">\n{caption}\n  </figcaption>'
        # Now alt - escape any double quotes
        alt = self.alt_textvariable.get().replace('"', "&quot;")
        if alt:
            alt = f' alt="{alt}"'
        # Create a unique ID from the filename
        image_id = os.path.splitext(os.path.basename(filename))[0]
        image_id = DiacriticRemover.remove_diacritics(image_id)
        # If ID already exists in file, try suffixes "_2", "_3", etc.
        id_base = image_id
        id_suffix = 1
        whole_file = IndexRange(maintext().start(), maintext().end())
        # Loop until we find an id that is not found in the file
        while maintext().find_match(f'id="{image_id}"', whole_file):
            id_suffix += 1
            image_id = f"{id_base}_{id_suffix}"
        # Alignment
        alignment = "figcenter"
        # Construct HTML
        html = f'<figure class="{alignment}" id="{image_id}">\n'
        html += f'  <img src="{filename}"{alt}>\n'
        html += f"{caption}\n</figure>\n"
        # Replace [Illustration...] with HTML
        maintext().undo_block_begin()
        maintext().replace(
            self.illo_range.start.index(), self.illo_range.end.index(), html
        )
        self.illo_range = None

    def clear_image(self) -> None:
        """Clear the image and reset variables accordingly."""
        if self.image:
            del self.image
        self.image = None
        if self.imagetk:
            del self.imagetk
        self.imagetk = None
        self.thumbnail.config(image="")
