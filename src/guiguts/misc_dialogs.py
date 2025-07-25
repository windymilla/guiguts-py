"""Miscellaneous dialogs."""

from importlib.metadata import version
import logging
import platform
import sys
import tkinter as tk
from tkinter import ttk, font, filedialog, messagebox, colorchooser
from typing import Literal, Optional, Callable
import unicodedata

from rapidfuzz import process
import regex as re

from guiguts.file import the_file
from guiguts.maintext import (
    maintext,
    menubar_metadata,
    EntryMetadata,
    KeyboardShortcutsDict,
    StyleDict,
    ColorKey,
)

from guiguts.mainwindow import ScrolledReadOnlyText, mainimage
from guiguts.preferences import (
    PrefKey,
    PersistentBoolean,
    PersistentInt,
    PersistentString,
    preferences,
)
from guiguts.root import root
from guiguts.utilities import is_mac, sound_bell, process_accel, IndexRange
from guiguts.widgets import (
    ToplevelDialog,
    ToolTip,
    insert_in_focus_widget,
    OkApplyCancelDialog,
    OkCancelDialog,
    mouse_bind,
    Combobox,
    Notebook,
    Busy,
    TreeviewList,
    ScrollableFrame,
    themed_style,
    set_global_font,
)

logger = logging.getLogger(__package__)

SEP_CHAR = "―"


class PreferencesDialog(ToplevelDialog):
    """A dialog that displays settings/preferences."""

    manual_page = "Edit_Menu#Preferences"
    COMBO_SEPARATOR = SEP_CHAR * 20

    def __init__(self) -> None:
        """Initialize preferences dialog."""
        super().__init__("Settings")

        # Set up tab notebook
        notebook = Notebook(self.top_frame)
        notebook.grid(column=0, row=0, sticky="NSEW")
        notebook.enable_traversal()

        # Appearance
        appearance_frame = ttk.Frame(notebook, padding=10)
        notebook.add(appearance_frame, text="Appearance")
        theme_frame = ttk.Frame(appearance_frame)
        theme_frame.grid(column=0, row=0, sticky="NSEW")
        theme_frame.columnconfigure(1, weight=1)
        ttk.Label(theme_frame, text="Theme (change requires restart): ").grid(
            column=0, row=0, sticky="NE"
        )
        cb = ttk.Combobox(
            theme_frame, textvariable=PersistentString(PrefKey.THEME_NAME)
        )
        cb.grid(column=1, row=0, sticky="NEW")
        cb["values"] = ["Default", "Dark", "Light"]
        cb["state"] = "readonly"
        ttk.Checkbutton(
            appearance_frame,
            text="High Contrast",
            variable=PersistentBoolean(PrefKey.HIGH_CONTRAST),
        ).grid(column=0, row=1, sticky="NEW", pady=5)
        tearoff_check = ttk.Checkbutton(
            appearance_frame,
            text="Use Tear-Off Menus (change requires restart)",
            variable=PersistentBoolean(PrefKey.TEAROFF_MENUS),
        )
        tearoff_check.grid(column=0, row=2, sticky="NEW", pady=5)
        if is_mac():
            tearoff_check["state"] = tk.DISABLED
            ToolTip(tearoff_check, "Not available on macOS")

        # Font
        def is_valid_font(new_value: str) -> bool:
            """Validation routine for Combobox - if separator has been selected,
            select Courier New instead.

            Args:
                new_value: New font family selected by user.

            Returns:
                True, because if invalid, it is fixed in this routine.
            """
            if new_value == self.COMBO_SEPARATOR:
                preferences.set(PrefKey.TEXT_FONT_FAMILY, "Courier")
                preferences.set(PrefKey.TEXT_FONT_FAMILY, "Courier New")
            return True

        ttk.Checkbutton(
            appearance_frame,
            text="Display Line Numbers",
            variable=PersistentBoolean(PrefKey.LINE_NUMBERS),
        ).grid(column=0, row=3, sticky="NEW", pady=5)
        ttk.Checkbutton(
            appearance_frame,
            text="Display Column Numbers",
            variable=PersistentBoolean(PrefKey.COLUMN_NUMBERS),
        ).grid(column=0, row=4, sticky="NEW", pady=5)
        ttk.Checkbutton(
            appearance_frame,
            text="Show Character Names in Status Bar",
            variable=PersistentBoolean(PrefKey.ORDINAL_NAMES),
        ).grid(column=0, row=5, sticky="NEW", pady=5)
        bell_frame = ttk.Frame(appearance_frame)
        bell_frame.grid(column=0, row=6, sticky="NEW", pady=(5, 0))
        ttk.Label(bell_frame, text="Warning bell: ").grid(column=0, row=0, sticky="NEW")
        ttk.Checkbutton(
            bell_frame,
            text="Audible",
            variable=PersistentBoolean(PrefKey.BELL_AUDIBLE),
        ).grid(column=1, row=0, sticky="NEW", padx=20)
        ttk.Checkbutton(
            bell_frame,
            text="Visual",
            variable=PersistentBoolean(PrefKey.BELL_VISUAL),
        ).grid(column=2, row=0, sticky="NEW")

        # Colors
        c_frame = ttk.Frame(notebook, padding=10)
        notebook.add(c_frame, text="Colors")
        c_frame.columnconfigure(0, weight=1)
        c_frame.rowconfigure(0, weight=1)
        self.colors_frame = ScrollableFrame(c_frame)
        self.colors_frame.grid(row=0, column=0)
        self.color_settings = maintext().get_colors()
        self.default_colors = maintext().get_default_colors()

        self.create_color_rows()
        self.theme_name = themed_style().theme_use()
        # Give main text a chance to update first
        self.bind(
            "<<ThemeChanged>>",
            lambda _: self.after_idle(lambda: self.create_color_rows(refresh=True)),
        )

        # Fonts
        font_frame = ttk.Frame(notebook, padding=10)
        notebook.add(font_frame, text="Fonts")
        font_frame.columnconfigure(1, weight=1)
        # font_frame.rowconfigure(0, weight=1)

        ttk.Label(font_frame, text="Text Window: ").grid(column=0, row=0, sticky="NEW")
        font_list = sorted(font.families(), key=str.lower)
        font_list.insert(0, self.COMBO_SEPARATOR)
        for preferred_font in "Courier New", "DejaVu Sans Mono", "DP Sans Mono":
            if preferred_font in font_list:
                font_list.insert(0, preferred_font)
            elif preferred_font == "Courier New" and "Courier" in font_list:
                font_list.insert(0, "Courier")
        cb = ttk.Combobox(
            font_frame,
            textvariable=PersistentString(PrefKey.TEXT_FONT_FAMILY),
            validate=tk.ALL,
            validatecommand=(self.register(is_valid_font), "%P"),
            values=font_list,
            state="readonly",
        )
        cb.grid(column=1, row=0, sticky="NSEW")

        spinbox = ttk.Spinbox(
            font_frame,
            textvariable=PersistentInt(PrefKey.TEXT_FONT_SIZE),
            from_=1,
            to=99,
            width=5,
        )
        spinbox.grid(column=2, row=0, sticky="NSEW", padx=2)
        ToolTip(spinbox, "Font size")

        def system_font_effects() -> None:
            """Handle toggling of system font checkbutton."""
            set_global_font()
            state = (
                tk.DISABLED
                if preferences.get(PrefKey.GLOBAL_FONT_SYSTEM)
                else tk.ACTIVE
            )
            self.global_font_family["state"] = state
            self.global_font_size["state"] = state

        ttk.Checkbutton(
            font_frame,
            text="Use System Font for Menus, Labels, Buttons, etc.",
            variable=PersistentBoolean(PrefKey.GLOBAL_FONT_SYSTEM),
            command=system_font_effects,
        ).grid(column=0, row=1, pady=(15, 0), columnspan=3, sticky="NSW")

        ttk.Label(font_frame, text="Menus, Labels & Buttons: ").grid(
            column=0, row=2, sticky="NSEW"
        )
        font_list = sorted(font.families(), key=str.lower)
        self.global_font_family = ttk.Combobox(
            font_frame,
            textvariable=PersistentString(PrefKey.GLOBAL_FONT_FAMILY),
            validate=tk.ALL,
            validatecommand=(self.register(is_valid_font), "%P"),
            values=font_list,
            state="readonly",
        )
        self.global_font_family.grid(column=1, row=2, sticky="NSEW")
        self.global_font_family.bind(
            "<<ComboboxSelected>>", lambda _e: set_global_font()
        )

        self.global_font_size = ttk.Spinbox(
            font_frame,
            textvariable=PersistentInt(PrefKey.GLOBAL_FONT_SIZE),
            command=set_global_font,
            from_=1,
            to=99,
            width=5,
        )
        self.global_font_size.grid(column=2, row=2, sticky="NSEW", padx=2)
        ToolTip(self.global_font_size, "Font size")
        system_font_effects()

        if is_mac():
            ttk.Label(
                font_frame,
                text="(May require restart to fully resize buttons & labels)",
            ).grid(column=0, row=3, columnspan=3, sticky="NSEW", pady=5)

        # Image Viewer
        image_viewer_frame = ttk.Frame(notebook, padding=10)
        notebook.add(image_viewer_frame, text="Image Viewer")
        image_viewer_frame.columnconfigure(0, weight=1)
        image_viewer_frame.columnconfigure(1, weight=1)

        dock_side_frame = ttk.Frame(image_viewer_frame)
        dock_side_frame.grid(column=0, row=0, sticky="NW", pady=5)
        ttk.Label(dock_side_frame, text="Dock Image Viewer on: ").grid(
            column=0, row=0, sticky="NW"
        )
        dock_side_textvariable = PersistentString(PrefKey.IMAGE_VIEWER_DOCK_SIDE)
        ttk.Radiobutton(
            dock_side_frame,
            text="Left",
            variable=dock_side_textvariable,
            value="left",
            command=lambda: mainimage().dock_func(),
        ).grid(column=1, row=0, sticky="NW", padx=20)
        ttk.Radiobutton(
            dock_side_frame,
            text="Right",
            variable=dock_side_textvariable,
            value="right",
            command=lambda: mainimage().dock_func(),
        ).grid(column=2, row=0, sticky="NW")

        iv_btn = ttk.Checkbutton(
            image_viewer_frame,
            text="Auto Img Reload Alert",
            variable=PersistentBoolean(PrefKey.IMAGE_VIEWER_ALERT),
        )
        iv_btn.grid(column=0, row=1, sticky="NEW", pady=5)
        ToolTip(
            iv_btn,
            "Whether to flash the border when Auto Img re-loads the\n"
            "default image after you manually select a different image",
        )
        ttk.Checkbutton(
            image_viewer_frame,
            text="Use External Viewer",
            variable=PersistentBoolean(PrefKey.IMAGE_VIEWER_EXTERNAL),
        ).grid(column=0, row=2, sticky="NEW", pady=5)
        file_name_frame = ttk.Frame(image_viewer_frame)
        file_name_frame.grid(row=3, column=0, columnspan=2, sticky="NSEW")
        file_name_frame.columnconfigure(0, weight=1)
        self.filename_textvariable = tk.StringVar(self, "")
        ttk.Entry(
            file_name_frame,
            textvariable=PersistentString(PrefKey.IMAGE_VIEWER_EXTERNAL_PATH),
            width=30,
        ).grid(row=0, column=0, sticky="NSEW", padx=(0, 2))

        def choose_external_viewer() -> None:
            """Choose program to view images."""
            if filename := filedialog.askopenfilename(
                parent=self, title="Choose Image Viewer"
            ):
                preferences.set(PrefKey.IMAGE_VIEWER_EXTERNAL_PATH, filename)

        ttk.Button(
            file_name_frame,
            text="Browse...",
            command=choose_external_viewer,
        ).grid(row=0, column=1, sticky="NSEW")

        def add_label_spinbox(
            frame: ttk.Frame, row: int, label: str, key: PrefKey, tooltip: str
        ) -> None:
            """Add a label and spinbox to given frame.
            Args:
                frame: Frame to add label & spinbox to.
                row: Which row in frame to add to.
                label: Text for label.
                key: Prefs key to use to store preference.
                tooltip: Text for tooltip.
            """
            ttk.Label(frame, text=label).grid(column=0, row=row, sticky="NSE", pady=2)
            spinbox = ttk.Spinbox(
                frame,
                textvariable=PersistentInt(key),
                from_=0,
                to=999,
                width=5,
            )
            spinbox.grid(column=1, row=row, sticky="NW", padx=5, pady=2)
            ToolTip(spinbox, tooltip)

        # Wrapping tab
        wrapping_frame = ttk.Frame(notebook, padding=10)
        notebook.add(wrapping_frame, text="Wrapping")

        add_label_spinbox(
            wrapping_frame,
            0,
            "Left Margin:",
            PrefKey.WRAP_LEFT_MARGIN,
            "Left margin for normal text",
        )
        add_label_spinbox(
            wrapping_frame,
            1,
            "Right Margin:",
            PrefKey.WRAP_RIGHT_MARGIN,
            "Right margin for normal text",
        )
        add_label_spinbox(
            wrapping_frame,
            2,
            "Blockquote Indent:",
            PrefKey.WRAP_BLOCKQUOTE_INDENT,
            "Extra indent for each level of /# blockquotes",
        )
        add_label_spinbox(
            wrapping_frame,
            3,
            "Blockquote Right Margin:",
            PrefKey.WRAP_BLOCKQUOTE_RIGHT_MARGIN,
            "Right margin for /# blockquotes",
        )
        add_label_spinbox(
            wrapping_frame,
            4,
            "Nowrap Block Indent:",
            PrefKey.WRAP_BLOCK_INDENT,
            "Indent for /* and /L blocks",
        )
        add_label_spinbox(
            wrapping_frame,
            5,
            "Poetry Indent:",
            PrefKey.WRAP_POETRY_INDENT,
            "Indent for /P poetry blocks",
        )
        add_label_spinbox(
            wrapping_frame,
            6,
            "Index Main Entry Margin:",
            PrefKey.WRAP_INDEX_MAIN_MARGIN,
            "Indent for main entries in index - sub-entries retain their indent relative to this",
        )
        add_label_spinbox(
            wrapping_frame,
            8,
            "Index Wrap Margin:",
            PrefKey.WRAP_INDEX_WRAP_MARGIN,
            "Left margin for all lines rewrapped in index",
        )
        add_label_spinbox(
            wrapping_frame,
            9,
            "Index Right Margin:",
            PrefKey.WRAP_INDEX_RIGHT_MARGIN,
            "Right margin for index entries",
        )

        # Advanced tab
        advance_frame = ttk.Frame(notebook, padding=10)
        notebook.add(advance_frame, text="Advanced")

        add_label_spinbox(
            advance_frame,
            0,
            "Text Line Spacing:",
            PrefKey.TEXT_LINE_SPACING,
            "Additional line spacing in text windows",
        )
        add_label_spinbox(
            advance_frame,
            1,
            "Text Cursor Width:",
            PrefKey.TEXT_CURSOR_WIDTH,
            "Width of insert cursor in main text window",
        )
        ttk.Checkbutton(
            advance_frame,
            text="Highlight Cursor Line",
            variable=PersistentBoolean(PrefKey.HIGHLIGHT_CURSOR_LINE),
        ).grid(column=0, row=2, sticky="NEW", pady=5)

        backup_btn = ttk.Checkbutton(
            advance_frame,
            text="Keep Backup Before Saving",
            variable=PersistentBoolean(PrefKey.BACKUPS_ENABLED),
        )
        backup_btn.grid(column=0, row=3, sticky="EW", pady=(10, 0))
        ToolTip(backup_btn, "Backup file will have '.bak' extension")
        ttk.Checkbutton(
            advance_frame,
            text="Enable Auto Save Every",
            variable=PersistentBoolean(PrefKey.AUTOSAVE_ENABLED),
            command=the_file().reset_autosave,
        ).grid(column=0, row=4, sticky="EW")
        spinbox = ttk.Spinbox(
            advance_frame,
            textvariable=PersistentInt(PrefKey.AUTOSAVE_INTERVAL),
            from_=1,
            to=60,
            width=3,
        )
        spinbox.grid(column=1, row=4, sticky="EW", padx=5)
        ToolTip(
            spinbox,
            "Autosave your file (with '.bk1', '.bk2' extensions) after this number of minutes",
        )
        ttk.Label(advance_frame, text="Minutes").grid(column=2, row=4, sticky="EW")
        ttk.Checkbutton(
            advance_frame,
            text="Show Tooltips",
            variable=PersistentBoolean(PrefKey.SHOW_TOOLTIPS),
        ).grid(column=0, row=5, sticky="NEW", pady=5)
        cqc = ttk.Checkbutton(
            advance_frame,
            text="Strict Single Curly Quote Conversion",
            variable=PersistentBoolean(PrefKey.CURLY_SINGLE_QUOTE_STRICT),
        )
        cqc.grid(column=0, row=6, sticky="NEW", pady=5)
        ToolTip(
            cqc,
            "On - only convert straight single quotes to curly if certain\n"
            "Off - convert some straight single quotes inside double quotes to apostrophes",
        )
        add_label_spinbox(
            advance_frame,
            7,
            "Regex timeout (seconds):",
            PrefKey.REGEX_TIMEOUT,
            "Longest time a regex search is allowed to take.\n"
            "This can be increased, or the regex changed, if it keeps timing out.",
        )
        ttk.Button(
            advance_frame,
            text="Reset shortcuts to default (change requires restart)",
            command=lambda: KeyboardShortcutsDict().reset(),
        ).grid(column=0, row=8, sticky="NSW", pady=5, columnspan=3)

        notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _: preferences.set(
                PrefKey.PREF_TAB_CURRENT, notebook.index(tk.CURRENT)
            ),
        )
        tab = preferences.get(PrefKey.PREF_TAB_CURRENT)
        if 0 <= tab < notebook.index(tk.END):
            notebook.select(tab)

    @classmethod
    def add_orphan_commands(cls) -> None:
        """Add orphan commands to command palette."""
        menubar_metadata().add_button_orphan(
            "Dark Theme", lambda: preferences.set(PrefKey.THEME_NAME, "Dark")
        )
        menubar_metadata().add_button_orphan(
            "Light Theme", lambda: preferences.set(PrefKey.THEME_NAME, "Light")
        )
        menubar_metadata().add_button_orphan(
            "Default Theme", lambda: preferences.set(PrefKey.THEME_NAME, "Default")
        )
        menubar_metadata().add_checkbutton_orphan(
            "High Contrast", PrefKey.HIGH_CONTRAST
        )
        if not is_mac():
            menubar_metadata().add_checkbutton_orphan(
                "Tear-Off Menus", PrefKey.TEAROFF_MENUS
            )
        menubar_metadata().add_checkbutton_orphan("Line Numbers", PrefKey.LINE_NUMBERS)
        menubar_metadata().add_checkbutton_orphan(
            "Column Numbers", PrefKey.COLUMN_NUMBERS
        )
        menubar_metadata().add_checkbutton_orphan(
            "Character Names in Status Bar", PrefKey.ORDINAL_NAMES
        )
        menubar_metadata().add_checkbutton_orphan("Audible Bell", PrefKey.BELL_AUDIBLE)
        menubar_metadata().add_checkbutton_orphan("Visual Bell", PrefKey.BELL_VISUAL)
        menubar_metadata().add_checkbutton_orphan(
            "Auto Img Reload Alert", PrefKey.IMAGE_VIEWER_ALERT
        )
        menubar_metadata().add_checkbutton_orphan(
            "Use External Viewer", PrefKey.IMAGE_VIEWER_EXTERNAL
        )
        menubar_metadata().add_checkbutton_orphan(
            "Highlight Cursor Line", PrefKey.HIGHLIGHT_CURSOR_LINE
        )
        menubar_metadata().add_checkbutton_orphan(
            "Keep Backup Before Saving", PrefKey.BACKUPS_ENABLED
        )
        menubar_metadata().add_checkbutton_orphan(
            "Enable Auto Save", PrefKey.AUTOSAVE_ENABLED
        )
        menubar_metadata().add_checkbutton_orphan("Tooltips", PrefKey.SHOW_TOOLTIPS)

    def create_color_rows(self, refresh: bool = False) -> None:
        """Create row of widgets for each configurable color.
        If widgets already exist, delete them first.

        Args:
            refresh: True if may want to destroy and recreate widgets because theme
                has changed.
        """
        # Don't refresh if theme change is not a change of name
        if refresh:
            if themed_style().theme_use() == self.theme_name:
                return
            self.theme_name = themed_style().theme_use()

        sample_tag_name = "sample_tag"
        dark_theme = themed_style().is_dark_theme()

        for widget in self.colors_frame.winfo_children():
            widget.destroy()

        for row, key in enumerate(self.color_settings):
            style_dict = (
                self.color_settings[key].dark
                if dark_theme
                else self.color_settings[key].light
            )
            default_dict = (
                self.default_colors[key].dark
                if dark_theme
                else self.default_colors[key].light
            )

            # Description sample as a Text widget
            desc = tk.Text(
                self.colors_frame,
                background=maintext()["background"],
                foreground=(
                    maintext()["selectforeground"]
                    if key == ColorKey.MAIN_SELECT_INACTIVE
                    else maintext()["foreground"]
                ),
                font=maintext()["font"],
                width=25,
                height=1,
                relief="flat",
                bd=0,
                exportselection=False,
                highlightthickness=0,
                padx=0,
                pady=0,
            )
            desc.grid(row=row, column=0, sticky="NSEW", padx=2, pady=2)
            desc.insert("1.0", self.color_settings[key].description)
            desc.bind(
                "<Enter>", lambda _, desc=desc: desc.see("1.0")  # type:ignore[misc]
            )
            desc.bind(
                "<Leave>", lambda _, desc=desc: desc.see("1.0")  # type:ignore[misc]
            )
            desc.tag_configure(sample_tag_name, style_dict)
            desc.tag_add(sample_tag_name, "1.0", "1.end")
            desc.tag_configure(
                "sel", foreground=desc["foreground"], background=desc["background"]
            )
            desc.config(inactiveselectbackground=desc["background"])
            desc.config(state="disabled")
            tooltip = ""
            if style_dict.get("foreground", "#000000") != "":
                tooltip += "Left-click to set text color. "
            if style_dict.get("background", "#000000") != "":
                tooltip += "Right-click or Shift-left-click to set background"
            ToolTip(desc, tooltip)

            # Colorpicker bindings
            def click_callback(
                attr: Literal["foreground", "background"],
                key: ColorKey = key,
                widget: tk.Text = desc,
                style_dict: StyleDict = style_dict,
            ) -> None:
                current = str(style_dict.get(attr, "#000000"))
                if current == "":
                    logger.error(f"{attr.capitalize()} color is not configurable")
                    return
                color = colorchooser.askcolor(
                    color=current, parent=self, title=f"Choose {attr} color"
                )[1]
                if color:
                    style_dict[attr] = color
                    widget.config(state="normal")
                    widget.tag_configure(sample_tag_name, style_dict)
                    widget.config(state="disabled")
                    self.update_color(key)

            mouse_bind(
                desc,
                "1",
                lambda _, cb=click_callback: cb("foreground"),  # type:ignore[misc]
            )
            mouse_bind(
                desc,
                "3",
                lambda _, cb=click_callback: cb("background"),  # type:ignore[misc]
            )
            mouse_bind(
                desc,
                "Shift+1",
                lambda _, cb=click_callback: cb("background"),  # type:ignore[misc]
            )

            # Underline toggle
            underline_var = tk.BooleanVar(
                value=bool(style_dict.get("underline", False))
            )

            def underline_callback(
                key: ColorKey = key,
                widget: tk.Text = desc,
                style_dict: StyleDict = style_dict,
                var: tk.BooleanVar = underline_var,
            ) -> None:
                style_dict["underline"] = "1" if var.get() else "0"
                widget.config(state="normal")
                widget.tag_configure(sample_tag_name, style_dict)
                widget.config(state="disabled")
                self.update_color(key)

            default_font_name = themed_style().lookup("TCheckbutton", "font")
            if not default_font_name:
                default_font_name = "TkDefaultFont"
            underline_font = font.Font(name=default_font_name, exists=True).copy()
            underline_font.configure(underline=True)
            themed_style().configure("Underline.TCheckbutton", font=underline_font)

            underline_btn = ttk.Checkbutton(
                self.colors_frame,
                text="U",
                command=underline_callback,
                variable=underline_var,
                state=tk.ACTIVE if self.color_settings[key].tag else tk.DISABLED,
                style="Underline.TCheckbutton",
            )
            underline_btn.grid(row=row, column=3, padx=2)
            ToolTip(underline_btn, "Underline text")

            # Border toggle
            border_var = tk.BooleanVar(value=bool(style_dict.get("borderwidth", 0)))

            def border_callback(
                key: ColorKey = key,
                widget: tk.Text = desc,
                style_dict: StyleDict = style_dict,
                var: tk.BooleanVar = border_var,
            ) -> None:
                border = var.get()
                style_dict["borderwidth"] = "2" if border else "0"
                style_dict["relief"] = tk.RIDGE if border else tk.FLAT
                widget.config(state="normal")
                widget.tag_configure(sample_tag_name, style_dict)
                widget.config(state="disabled")
                self.update_color(key)

            border_btn = ttk.Checkbutton(
                self.colors_frame,
                text="⬜",
                command=border_callback,
                variable=border_var,
                state=tk.ACTIVE if self.color_settings[key].tag else tk.DISABLED,
            )
            border_btn.grid(row=row, column=4, padx=2)
            ToolTip(border_btn, "Add border to text")

            # Reset button
            def reset_callback(
                key: ColorKey = key,
                widget: tk.Text = desc,
                default_dict: StyleDict = default_dict,
                style_dict: StyleDict = style_dict,
                underline_var: tk.BooleanVar = underline_var,
                border_var: tk.BooleanVar = border_var,
            ) -> None:
                style_dict.clear()
                style_dict.update(default_dict)
                if self.color_settings[key].tag:
                    if "underline" not in default_dict:
                        style_dict["underline"] = False
                    if "borderwidth" not in default_dict:
                        style_dict["borderwidth"] = 0
                    if "relief" not in default_dict:
                        style_dict["relief"] = tk.FLAT
                    underline_var.set(bool(style_dict["underline"]))
                    border_var.set(bool(style_dict["borderwidth"]))

                widget.config(state="normal")
                widget.tag_configure(sample_tag_name, style_dict)
                widget.config(state="disabled")
                self.update_color(key)

            reset_btn = ttk.Button(
                self.colors_frame, text="Reset", command=reset_callback
            )
            reset_btn.grid(row=row, column=5, padx=2)
            ToolTip(reset_btn, "Restore default appearnce")

    def update_color(self, color_key: ColorKey) -> None:
        """Update everywhere that needs to know about color change.

        Args:
            color_key: Key of color that has been changed.
        """
        self.color_settings[color_key].update_func(color_key)
        maintext().save_colors_to_prefs()


class HelpAboutDialog(ToplevelDialog):
    """A "Help About Guiguts" dialog with version numbers."""

    manual_page = ""  # Main manual page

    def __init__(self) -> None:
        """Initialize preferences dialog."""
        super().__init__("Help About Guiguts", resize_x=False, resize_y=False)

        # Default font is monospaced. Helvetica is guaranteed to give a proportional font
        font_family = "Helvetica"
        font_small = 10
        font_medium = 12
        font_large = 14
        title_start = "1.0"
        title_end = "2.0 lineend"
        version_start = "3.0"
        version_end = "9.0"

        def copy_to_clipboard() -> None:
            """Copy text to clipboard."""
            maintext().clipboard_clear()
            maintext().clipboard_append(self.text.get(version_start, version_end))

        copy_button = ttk.Button(
            self.top_frame,
            text="Copy Version Information to Clipboard",
            command=copy_to_clipboard,
        )
        copy_button.grid(row=0, column=0, pady=(5, 5))
        self.text = ScrolledReadOnlyText(
            self.top_frame, wrap=tk.NONE, font=(font_family, font_small)
        )
        self.text.grid(row=1, column=0, sticky="NSEW")
        ToolTip(
            self.text,
            "Copy version information when reporting issues",
            use_pointer_pos=True,
        )

        self.text.insert(
            tk.END,
            f"""Guiguts - an application to support creation of ebooks for PG

Guiguts version: {version('guiguts')}

Python version: {sys.version}
Tk/Tcl version: {root().call("info", "patchlevel")}
OS Platform: {platform.platform()}
OS Release: {platform.release()}



Copyright Contributors to the Guiguts-py project.

This program is free software; you can redistribute it
and/or modify it under the terms of the GNU General Public
License as published by the Free Software Foundation;
either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be
useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 51 Franklin Street,
Fifth Floor, Boston, MA 02110-1301 USA.""",
        )
        self.text.tag_add("title_tag", title_start, title_end)
        self.text.tag_config("title_tag", font=(font_family, font_large))
        self.text.tag_add("version_tag", version_start, version_end)
        self.text.tag_config("version_tag", font=(font_family, font_medium))


_compose_dict: dict[str, str] = {}


class ComposeSequenceDialog(OkApplyCancelDialog):
    """Dialog to enter Compose Sequences.

    Attributes:
        dict: Dictionary mapping sequence of keystrokes to character.
    """

    manual_page = "Tools_Menu#Compose_Sequence"

    def __init__(self) -> None:
        """Initialize compose sequence dialog."""
        super().__init__("Compose Sequence", resize_x=False, resize_y=False)
        ttk.Label(self.top_frame, text="Compose: ").grid(column=0, row=0, sticky="NSEW")
        self.string = tk.StringVar()
        self.entry = Combobox(
            self.top_frame, PrefKey.COMPOSE_HISTORY, textvariable=self.string
        )
        # self.entry = ttk.Entry(self.top_frame, textvariable=self.string, name="entry1")
        self.entry.grid(column=1, row=0, sticky="NSEW")
        # In tkinter, binding order is widget, class, toplevel, all
        # Swap first two, so that class binding has time to set textvariable
        # before the widget binding below is executed.
        bindings = self.entry.bindtags()
        self.entry.bindtags((bindings[1], bindings[0], bindings[2], bindings[3]))
        self.entry.bind("<Key>", lambda _event: self.interpret_and_insert())
        self.entry.focus()
        init_compose_dict()

    def apply_changes(self) -> bool:
        """Overridden function called when Apply/OK buttons are pressed.

        Call to attempt to interpret compose sequence

        Returns:
            Always returns True, meaning OK button (or Return key) will close dialog.
        """
        self.interpret_and_insert(force=True)
        self.entry.select_range(0, tk.END)
        return True

    def interpret_and_insert(self, force: bool = False) -> None:
        """Interpret string from Entry field as a compose sequence and insert it.

        If compose sequence is complete, then the composed character will be
        inserted in the most recently focused text/entry widget and the Compose
        dialog will be closed. If sequence is not complete, then nothing will be done,
        unless `force` is True.

        Args:
            force: True if string should be interpreted/inserted as-is,
                rather than waiting for further input.
        """
        sequence = self.string.get()
        char = ""
        # First check if sequence is in dictionary
        if sequence in _compose_dict:
            char = _compose_dict[sequence]
        elif match := re.fullmatch(r"[0-9a-f]{4}", sequence, re.IGNORECASE):
            # Exactly 4 hex digits translates to a single Unicode character
            char = chr(int(sequence, 16))
        elif force:
            if match := re.fullmatch(
                r"(0x|\\x|x|U\+?)?([0-9a-fA-F]{2,})", sequence, re.IGNORECASE
            ):
                # Or user can force interpretation as hex with fewer than 4 digits,
                # or with more than 4 by using a prefix: 0x, \x, x, U or U+
                char = chr(int(match[2], 16))
            elif match := re.fullmatch(r"#(\d{2,})", sequence):
                # Or specify in decimal following '#' character
                char = chr(int(match[1]))
        # Don't insert anything if no match
        if not char:
            return
        insert_in_focus_widget(char)
        self.entry.add_to_history(self.string.get())
        if not force:
            self.destroy()


def init_compose_dict() -> None:
    """Initialize dictionary of compose sequences."""
    if _compose_dict:
        return  # Already initialized
    init_char_reversible("‘", "'<")
    init_char_reversible("’", "'>")
    init_char_reversible("“", '"<')
    init_char_reversible("”", '">')
    init_chars("±", "+-")
    init_chars("·", "^.", "*.", ".*")
    init_chars("×", "*x", "x*")
    init_chars("÷", ":-")
    init_char_reversible("°", "oo", "*o")
    init_char_reversible("′", "1'")
    init_char_reversible("″", "2'")
    init_char_reversible("‴", "3'")
    init_char_reversible(" ", "  ", "* ")
    init_chars("—", "--")
    init_char_reversible("–", "- ")
    init_chars("⁂", "**")
    init_char_reversible("º", "o_")
    init_char_reversible("ª", "a_")
    init_chars("‖", "||")
    init_chars("¡", "!!")
    init_chars("¿", "??")
    init_chars("«", "<<")
    init_chars("»", ">>")
    init_char_case("Æ", "AE")
    init_char_case("Œ", "OE")
    init_char_case("ẞ", "SS")
    init_char_case("Ð", "DH", "ETH")
    init_char_case("Þ", "TH")
    init_chars("©", "(c)", "(C)")
    init_chars("†", "dag", "DAG")
    init_chars("‡", "ddag", "DDAG")
    init_accent("£", "L", "-")
    init_accent("¢", "C", "/", "|")
    init_chars("§", "sec", "s*", "*s", "SEC", "S*", "*S")
    init_chars("¶", "pil", "p*", "*p", "PIL", "P*", "*P")
    init_chars("ſ", "sf", "SF")
    init_chars("‚", ",'")
    init_chars("‛", "^'")
    init_chars("„", ',"')
    init_chars("‟", '^"')
    init_chars("½", "1/2")
    init_chars("⅓", "1/3")
    init_chars("⅔", "2/3")
    init_chars("¼", "1/4")
    init_chars("¾", "3/4")
    init_chars("⅕", "1/5")
    init_chars("⅖", "2/5")
    init_chars("⅗", "3/5")
    init_chars("⅘", "4/5")
    init_chars("⅙", "1/6")
    init_chars("⅚", "5/6")
    init_chars("⅐", "1/7")
    init_chars("⅛", "1/8")
    init_chars("⅜", "3/8")
    init_chars("⅝", "5/8")
    init_chars("⅞", "7/8")
    init_chars("⅑", "1/9")
    init_chars("⅒", "1/10")
    for num, char in enumerate("⁰¹²³⁴⁵⁶⁷⁸⁹"):
        init_chars(char, f"^{num}")
    for num, char in enumerate("₀₁₂₃₄₅₆₇₈₉"):
        init_chars(char, f",{num}")

    # Accented characters
    init_accent("À", "A", "`", "\\")
    init_accent("Á", "A", "'", "/")
    init_accent("Â", "A", "^")
    init_accent("Ã", "A", "~")
    init_accent("Ä", "A", '"', ":")
    init_accent("Å", "A", "o", "*")
    init_accent("Ā", "A", "-", "=")
    init_accent("È", "E", "`", "\\")
    init_accent("É", "E", "'", "/")
    init_accent("Ê", "E", "^")
    init_accent("Ë", "E", '"', ":")
    init_accent("Ē", "E", "-", "=")
    init_accent("Ì", "I", "`", "\\")
    init_accent("Í", "I", "'", "/")
    init_accent("Î", "I", "^")
    init_accent("Ï", "I", '"', ":")
    init_accent("Ī", "I", "-", "=")
    init_accent("Ò", "O", "`", "\\")
    init_accent("Ó", "O", "'")
    init_accent("Ô", "O", "^")
    init_accent("Õ", "O", "~")
    init_accent("Ö", "O", '"', ":")
    init_accent("Ø", "O", "/")
    init_accent("Ō", "O", "-", "=")
    init_accent("Ù", "U", "`", "\\")
    init_accent("Ú", "U", "'", "/")
    init_accent("Û", "U", "^")
    init_accent("Ü", "U", '"', ":")
    init_accent("Ū", "U", "-", "=")
    init_accent("Ç", "C", ",")
    init_accent("Ñ", "N", "~")
    init_accent("Ÿ", "Y", '"', ":")
    init_accent("Ý", "Y", "'", "/")

    # Combining characters
    init_combining("\u0300", "\u0316", "\\", "`")  # grave
    init_combining("\u0301", "\u0317", "/", "'")  # acute
    init_combining("\u0302", "\u032d", "^")  # circumflex
    init_combining("\u0303", "\u0330", "~")  # tilde
    init_combining("\u0304", "\u0331", "-", "=")  # macron
    init_combining("\u0306", "\u032e", ")")  # breve
    init_combining("\u0311", "\u032f", "(")  # inverted breve
    init_combining("\u0307", "\u0323", ".")  # dot
    init_combining("\u0308", "\u0324", ":", '"')  # diaresis
    init_combining("\u0309", "", "?")  # hook above
    init_combining("\u030a", "\u0325", "*")  # ring
    init_combining("\u030c", "\u032c", "v")  # caron
    init_combining("", "\u0327", ",")  # cedilla
    init_combining("", "\u0328", ";")  # ogonek

    # Greek characters
    init_greek_alphabet()
    init_greek_accent("Ὰ", "A", "ᾼ")
    init_greek_accent("Ὲ", "E")
    init_greek_accent("Ὴ", "H", "ῌ")
    init_greek_accent("Ὶ", "I")
    init_greek_accent("Ὸ", "O")
    init_greek_accent("Ὺ", "U")
    init_greek_accent("Ὼ", "W", "ῼ")
    init_greek_breathing("Ἀ", "A", "ᾈ")
    init_greek_breathing("Ἐ", "E")
    init_greek_breathing("Ἠ", "H", "ᾘ")
    init_greek_breathing("Ἰ", "I")
    init_greek_breathing("Ὀ", "O")
    init_greek_breathing("὘", "U")
    init_greek_breathing("Ὠ", "W", "ᾨ")


def init_accent(char: str, base: str, *accents: str) -> None:
    """Add entries to the dictionary for upper & lower case versions
    of the given char, using each of the accents.

    Args:
        char: Upper case version of character to be added.
        base: Upper case base English character to be accented.
        *accents: Characters that can be used to add the accent.
    """
    for accent in accents:
        init_char_case(char, base + accent)
        init_char_case(char, accent + base)


def init_chars(char: str, *sequences: str) -> None:
    """Add entries to the dictionary for the given char.

    Args:
        char: Character to be added.
        *sequences: Sequences of keys to generate the character.
    """
    for sequence in sequences:
        _compose_dict[sequence] = char


def init_char_reversible(char: str, *sequences: str) -> None:
    """Add entries to the dictionary for the given char with
    2 reversible characters per sequence.

    Args:
        char: Character to be added.
        *sequences: Sequences of reversible keys to generate the character.
    """
    for sequence in sequences:
        _compose_dict[sequence] = char
        _compose_dict[sequence[::-1]] = char


def init_char_case(char: str, *sequences: str) -> None:
    """Add upper & lower case entries to the dictionary for the given char & sequence.

    Args:
        char: Character to be added.
        *sequences: Sequences of keys to generate the character.
    """
    lchar = char.lower()
    for sequence in sequences:
        lsequence = sequence.lower()
        _compose_dict[sequence] = char
        _compose_dict[lsequence] = lchar


def init_combining(above: str, below: str, *accents: str) -> None:
    """Add entries to the dictionary for combining characters.

    Args:
        above: Combining character above (empty if none to be added).
        base: Combining character below (empty if none to be added).
        *accents: Characters that follow `+` and `_` to create the combining characters.
    """
    for accent in accents:
        if above:
            _compose_dict["+" + accent] = above
        if below:
            _compose_dict["_" + accent] = below


def init_greek_alphabet() -> None:
    """Add entries to the dictionary for non-accented Greek alphabet letters.

    Greek letter sequences are prefixed with `=` sign.
    """
    ualpha = ord("Α")
    lalpha = ord("α")
    for offset, base in enumerate("ABGDEZHQIKLMNXOPRJSTUFCYW"):
        _compose_dict["=" + base] = chr(ualpha + offset)
        _compose_dict["=" + base.lower()] = chr(lalpha + offset)


def init_greek_accent(char: str, base: str, uiota: str = "") -> None:
    """Add varia & oxia accented Greek letters to dictionary.

    Greek letter sequences are prefixed with `=` sign.

    Args:
        char: Upper case version of character with varia to be added.
            Next ordinal gives the character with oxia.
        base: Upper case base English character to be accented.
        uiota: Optional upper case version of character with iota subscript.
            Prev & next ordinals give same with accents for lower case only.
            Note there is no upper case with accent and iota, and not all
            vowels have an iota version.
    """
    _compose_dict["=\\" + base] = _compose_dict["=`" + base] = char
    _compose_dict["=/" + base] = _compose_dict["='" + base] = chr(ord(char) + 1)
    lbase = base.lower()
    lchar = char.lower()
    _compose_dict["=\\" + lbase] = _compose_dict["=`" + lbase] = lchar
    _compose_dict["=/" + lbase] = _compose_dict["='" + lbase] = chr(ord(lchar) + 1)
    if not uiota:
        return
    _compose_dict["=|" + base] = uiota
    liota = uiota.lower()
    _compose_dict["=|" + lbase] = liota
    _compose_dict["=\\|" + lbase] = _compose_dict["=`|" + lbase] = chr(ord(liota) - 1)
    _compose_dict["=/|" + lbase] = _compose_dict["='|" + lbase] = chr(ord(liota) + 1)


def init_greek_breathing(char: str, base: str, uiota: str = "") -> None:
    """Add accented Greek letters including breathing to dictionary.

    Greek letter sequences are prefixed with `=` sign.

    Args:
        char: Upper case char in middle group of 16, e.g. alpha with various accents.
        base: Upper case base English character to be accented.
        iota: Optional upper case verison with iota subscript if needed.
    """
    lbase = base.lower()
    ord_list = (ord(char), ord(uiota)) if uiota else (ord(char),)
    for char_ord in ord_list:
        _compose_dict["=)" + base] = chr(char_ord)
        _compose_dict["=(" + base] = chr(char_ord + 1)
        _compose_dict["=(`" + base] = _compose_dict["=(\\" + base] = chr(char_ord + 2)
        _compose_dict["=)`" + base] = _compose_dict["=)\\" + base] = chr(char_ord + 3)
        _compose_dict["=('" + base] = _compose_dict["=(/" + base] = chr(char_ord + 4)
        _compose_dict["=)'" + base] = _compose_dict["=)/" + base] = chr(char_ord + 5)
        _compose_dict["=(^" + base] = _compose_dict["=(~" + base] = chr(char_ord + 6)
        _compose_dict["=)^" + base] = _compose_dict["=)~" + base] = chr(char_ord + 7)
        _compose_dict["=)" + lbase] = chr(char_ord - 8)
        _compose_dict["=(" + lbase] = chr(char_ord - 7)
        _compose_dict["=(`" + lbase] = _compose_dict["=(\\" + lbase] = chr(char_ord - 6)
        _compose_dict["=)`" + lbase] = _compose_dict["=)\\" + lbase] = chr(char_ord - 5)
        _compose_dict["=('" + lbase] = _compose_dict["=(/" + lbase] = chr(char_ord - 4)
        _compose_dict["=)'" + lbase] = _compose_dict["=)/" + lbase] = chr(char_ord - 3)
        _compose_dict["=(^" + lbase] = _compose_dict["=(~" + lbase] = chr(char_ord - 2)
        _compose_dict["=)^" + lbase] = _compose_dict["=)~" + base] = chr(char_ord - 1)
        # Add iota sequence character in case going round loop a second time
        base = "|" + base
        lbase = "|" + lbase


class ComposeHelpDialog(ToplevelDialog):
    """A dialog to show the compose sequences."""

    manual_page = "Tools_Menu#Compose_Sequence"

    def __init__(self) -> None:
        """Initialize class members from page details."""
        super().__init__("List of Compose Sequences")

        self.column_headings = ("Character", "Sequence", "Name")
        widths = (70, 70, 600)
        self.help = TreeviewList(
            self.top_frame,
            columns=self.column_headings,
        )
        ToolTip(
            self.help,
            "Click (or press Space or Return) to insert character",
            use_pointer_pos=True,
        )
        for col, column in enumerate(self.column_headings):
            self.help.column(
                f"#{col + 1}",
                minwidth=10,
                width=widths[col],
                stretch=True,
                anchor=tk.W,
            )
            self.help.heading(
                f"#{col + 1}",
                text=column,
                anchor=tk.W,
            )
        self.help.grid(row=0, column=0, sticky=tk.NSEW)

        self.scrollbar = ttk.Scrollbar(
            self.top_frame, orient=tk.VERTICAL, command=self.help.yview
        )
        self.help.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid(row=0, column=1, sticky=tk.NS)

        mouse_bind(self.help, "1", self.insert_char)
        self.bind("<Return>", lambda _: self.insert_char(None))
        self.bind("<space>", lambda _: self.insert_char(None))
        self.help.focus_force()

        init_compose_dict()

        # Avoid displaying help for reversed 2-char sequence, e.g. "o*" and "*o"
        # Remember ones that have been entered already
        reverse_done = {}
        for sequence, char in _compose_dict.items():
            seq_display = sequence.replace(" ", "␣")
            if len(sequence) == 2:
                rev_sequence = sequence[::-1]
                if rev_sequence in reverse_done:
                    continue
                rev_char = _compose_dict.get(rev_sequence)
                if rev_char == char and rev_sequence != sequence:
                    seq_display += f"  or  {rev_sequence.replace(' ', '␣')}"
                    reverse_done[sequence] = char
            # Don't add uppercase version if it leads to identical character, e.g. "dag"/"DAG" for dagger
            if (
                char == _compose_dict.get(sequence.lower())
                and sequence != sequence.lower()
            ):
                continue
            try:
                name = unicodedata.name(char)
            except ValueError:
                continue  # Some Greek combinations don't exist
            entry = (char, seq_display, name)
            self.help.insert("", tk.END, values=entry)

        children = self.help.get_children()
        if children:
            self.help.select_and_focus_by_index(0)
            self.help.see(children[0])

    def insert_char(self, event: Optional[tk.Event]) -> None:
        """Insert character corresponding to row clicked.

        Args:
            event: Event containing location of mouse click. If None, use focused row.
        """
        if event is None:
            row_id = self.help.focus()
            if not row_id:
                return
        else:
            row_id, _ = self.help.identify_rowcol(event)
        row = self.help.set(row_id)
        try:
            char = row[self.column_headings[0]]
        except KeyError:
            return
        insert_in_focus_widget(char)


class RecentPlusEntry:
    """Class to store recent-ness plus a command structure."""

    NONRECENT = 10000
    SEPARATOR = 1000  # Between NONRECENT and valid recentnesses
    PREFIXMATCH = 100
    SUBSTRMATCH = 90
    MENUMATCH = 80

    def __init__(self, recentness: int, entry: EntryMetadata) -> None:
        self.recentness = recentness
        self.entry = entry


class CommandEditDialog(OkCancelDialog):
    """Command Edit Dialog."""

    manual_page = "Help_Menu#User-defined_Keyboard_Shortcuts"

    # Define which keys count as modifiers
    MODIFIER_KEYS = {
        "Shift_L": "Shift",
        "Shift_R": "Shift",
        "Control_L": "Ctrl",
        "Control_R": "Ctrl",
        "Alt_L": "Option" if is_mac() else "Alt",
        "Alt_R": "Option" if is_mac() else "Alt",
        "Meta_L": "Cmd",
        "Meta_R": "Cmd",
        "Option_L": "Option",
        "Option_R": "Option",
    }

    # On macOS, "Cmd+-" or "Cmd+Key--" causes problems, so use name
    KEY_NAMES = {"-": "minus"}

    def __init__(self, command_dlg: "CommandPaletteDialog") -> None:
        """Initialize the command edit window."""
        super().__init__(
            "Shortcut Edit", display_apply=False, resize_x=False, resize_y=False
        )

        self.cmd_dlg = command_dlg
        ttk.Label(self.top_frame, text="Label:").grid(
            row=0, column=0, sticky="NSEW", pady=2
        )
        self.label_variable = tk.StringVar()
        ttk.Entry(
            self.top_frame, textvariable=self.label_variable, state="readonly", width=40
        ).grid(row=0, column=1, sticky="NSEW", pady=2)
        ttk.Label(self.top_frame, text="Menu:").grid(
            row=1, column=0, sticky="NSEW", pady=2
        )
        self.menu_variable = tk.StringVar()
        ttk.Entry(
            self.top_frame, textvariable=self.menu_variable, state="readonly", width=40
        ).grid(row=1, column=1, sticky="NSEW", pady=2)
        ttk.Label(self.top_frame, text="Shortcut:").grid(
            row=2, column=0, sticky="NSEW", pady=2
        )
        self._shortcut = ""
        self.shortcut_variable = tk.StringVar()  # For display only
        shortcut_entry = ttk.Entry(
            self.top_frame,
            textvariable=self.shortcut_variable,
            state="readonly",
        )
        shortcut_entry.grid(row=2, column=1, sticky="NSEW", pady=2)
        ToolTip(
            shortcut_entry,
            "Press required modifiers and keyboard key to use for shortcut",
        )
        shortcut_entry.focus()

        # Just used for test binding
        self.dummy_widget = ttk.Label(self.top_frame)

        # Track which modifier keys are currently pressed
        self.pressed_modifiers: set[str] = set()
        self.bind("<KeyPress>", self.key_press)
        self.bind("<KeyRelease>", self.key_release)
        # Explicitly unbind Return, so it is treated like other keypresses
        self.unbind("<Return>")
        # Clear modifiers if dialog loses focus, particularly via Alt-tab on Windows
        self.bind("<FocusOut>", lambda _: self.pressed_modifiers.clear())

        self.cmd = EntryMetadata("", "", "")

    @property
    def shortcut(self) -> str:
        """Current shortcut. When assigned to, updates shortcut display variable."""
        return self._shortcut

    @shortcut.setter
    def shortcut(self, value: str) -> None:
        self._shortcut = value
        display_shortcut = process_accel(value)[0]
        self.shortcut_variable.set(display_shortcut)

    def load(self, cmd: EntryMetadata) -> None:
        """Load dialog with values from given command."""
        self.cmd = cmd
        self.label_variable.set(self.cmd.display_label())
        self.menu_variable.set(self.cmd.display_parent_label())
        self.shortcut = self.cmd.shortcut

    def apply_changes(self) -> bool:
        """Save shortcut from dialog into current cmd.

        Returns:
            True if successful.
        """
        new_shortcut = self.shortcut
        display_shortcut = process_accel(new_shortcut)[0]
        # Don't allow shortcuts that don't use Ctrl/Cmd/Alt except for F keys
        if (
            display_shortcut
            and not any(m in display_shortcut for m in ["Ctrl", "Cmd", "Alt"])
            and not re.search(r"F\d+$", display_shortcut)
        ):
            logger.error(
                f"Shortcut must include Ctrl or {'Cmd' if is_mac() else 'Alt'}"
            )
            self.lift()
            self.focus()
            return False

        # Don't allow shortcuts that use Option or Tab
        for key in ("Option", "Tab"):
            if key.lower() in display_shortcut.lower():
                logger.error(f"{key} key may not be used for shortcuts")
                self.lift()
                self.focus()
                return False

        # Plain F1 is reserved
        if display_shortcut == "F1":
            logger.error(
                f"F1 without Shift, Ctrl or {'Cmd' if is_mac() else 'Alt'} is reserved for Help"
            )
            self.lift()
            self.focus()
            return False

        # Cmd+Shift+? is reserved for Help too
        if display_shortcut == "Cmd+Shift+?":
            logger.error("Cmd+Shift+? is reserved for Help")
            self.lift()
            self.focus()
            return False

        # Other reserved shortcuts
        ctrl_cmd = "Cmd" if is_mac() else "Ctrl"
        for res_key in ("A", "C", "V", "X"):
            if display_shortcut == f"{ctrl_cmd}+{res_key}":
                logger.error(
                    f"{display_shortcut} is a reserved shortcut and may not be reassigned"
                )
                self.lift()
                self.focus()
                return False

        # Bind do_nothing to dummy widget, to test if the bind sequence is legal
        def do_nothing(_: tk.Event) -> None:
            """Do nothing."""

        if new_shortcut:
            try:
                test_key = process_accel(new_shortcut)[1]
                self.dummy_widget.bind(test_key, do_nothing)
                self.dummy_widget.unbind(test_key)
            except tk.TclError:
                logger.error(
                    f"Key combination {test_key} is not supported as a shortcut."
                )
                self.lift()
                self.focus()
                return False

        shortcuts_dict = KeyboardShortcutsDict()

        menu = self.menu_variable.get()
        label = self.label_variable.get()
        new_assign = f"{menu}|{label}" if menu else label

        # If shortcut is already assigned, check whether user wants to continue
        command = menubar_metadata().metadata_from_shortcut(
            process_accel(new_shortcut)[0]
        )
        if command is None:
            shortcut_used = False
        else:
            shortcut_used = True
            menu = command.display_parent_label()
            label = command.display_label()
            cur_assign = f"{menu}|{label}" if menu else label
            if cur_assign != new_assign:
                if not messagebox.askyesno(
                    title="Shortcut Already Assigned",
                    message=f'"{self.shortcut_variable.get()}" is currently assigned to\n"{cur_assign}".',
                    detail=f'Reassign it to "{new_assign}" instead?',
                    default=messagebox.NO,
                    icon=messagebox.WARNING,
                ):
                    return False
                # Reset current shortcut assignment to avoid duplicates
                command.shortcut = ""
                # Also set in shortcuts_dict which is saved to prefs below
                shortcuts_dict.set_shortcut(
                    command.label, command.parent_label, command.shortcut
                )
        if not is_mac() and not shortcut_used:
            if match := re.fullmatch(r"Alt\+(.)", process_accel(new_shortcut)[0]):
                for top_menu in menubar_metadata().entries:
                    if f"~{match[1]}" in top_menu.label:
                        if not messagebox.askyesno(
                            title="Shortcut Already Assigned",
                            message=f'"{self.shortcut_variable.get()}" currently opens the {top_menu.label.replace("~", "")} menu.',
                            detail=f'Reassign it to "{new_assign}" instead?',
                            default=messagebox.NO,
                            icon=messagebox.WARNING,
                        ):
                            return False

        # Update prefs
        shortcuts_dict.set_shortcut(self.cmd.label, self.cmd.parent_label, new_shortcut)
        shortcuts_dict.save_to_prefs()
        # Update metadata
        self.cmd.shortcut = new_shortcut
        # Refresh command palette
        if self.cmd_dlg.winfo_exists():
            self.cmd_dlg.update_list()
        # Refresh menus
        assert CommandPaletteDialog.recreate_menus_callback is not None
        CommandPaletteDialog.recreate_menus_callback()  # pylint: disable=not-callable
        return True

    def key_press(self, event: tk.Event) -> str:
        """Handle keystroke in dialog."""
        keysym = event.keysym
        # Just flag modifier keys as pressed
        if keysym in self.MODIFIER_KEYS:
            self.pressed_modifiers.add(keysym)
        # Plain Backspace & Delete remove the shortcut
        elif keysym in ("BackSpace", "Delete") and len(self.pressed_modifiers) == 0:
            self.shortcut = ""
        # Plain Return performs OK action
        elif keysym == "Return" and len(self.pressed_modifiers) == 0:
            self.ok_pressed()
        # Allow tab keystrokes to perform focus-next/prev action by returning ""
        elif keysym == "Tab":
            return ""
        # All other keys potentially OK for shortcut
        else:
            # Combine the current modifiers with the key
            mods = sorted(set(self.MODIFIER_KEYS[kk] for kk in self.pressed_modifiers))
            # Substitute any keys that cause problems if just the key character is used
            keysym = CommandEditDialog.KEY_NAMES.get(keysym, keysym)
            # Regular character key
            if len(keysym) == 1:
                keysym = f"Key-{keysym.upper()}"
            # Combine modifiers & key to create shortcut
            self.shortcut = "+".join(mods + [keysym])
        return "break"

    def key_release(self, event: tk.Event) -> str:
        """Handle key release in dialog."""
        key = event.keysym
        if key in self.MODIFIER_KEYS:
            self.pressed_modifiers.discard(key)
        return "break"


class CommandPaletteDialog(ToplevelDialog):
    """Command Palette Dialog."""

    manual_page = "Help_Menu#Command_Palette"
    NUM_HISTORY = 5
    SEPARATOR_TAG = "separator"
    recreate_menus_callback: Optional[Callable] = None

    def __init__(self) -> None:
        """Initialize the command palette window."""
        super().__init__("Command Palette")
        self.commands = menubar_metadata().get_all_palette_commands()
        self.filtered_entries: list[RecentPlusEntry] = []
        self.num_recent = 0
        self.edit_dialog: Optional[CommandEditDialog] = None

        self.top_frame.grid_rowconfigure(0, weight=0)
        self.top_frame.grid_rowconfigure(1, weight=1)

        entry_frame = ttk.Frame(self.top_frame)
        entry_frame.grid(row=0, column=0, sticky="NSEW", columnspan=2)
        entry_frame.columnconfigure(0, weight=1)
        entry_frame.columnconfigure(1, uniform="same")
        entry_frame.columnconfigure(2, uniform="same")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda _1, _2, _3: self.update_list())
        self.entry = ttk.Entry(entry_frame, textvariable=self.search_var)
        self.entry.grid(row=0, column=0, padx=5, pady=5, sticky="NSEW")
        ToolTip(self.entry, "Type part of a command to filter the list")
        ttk.Button(
            entry_frame,
            text="Run",
            command=self.execute_command,
        ).grid(row=0, column=1, sticky="NSEW", padx=(0, 2))
        ttk.Button(
            entry_frame,
            text="Edit Shortcut",
            command=self.edit_command,
        ).grid(row=0, column=2, sticky="NSEW", padx=(2, 0))

        columns = ("Command", "Shortcut", "Menu")
        widths = (250, 120, 100)
        self.list = TreeviewList(
            self.top_frame,
            columns=columns,
        )
        ToolTip(
            self.list,
            "Type part of a command to filter the list\n"
            "Double click (or press Return) to execute command.",
        )
        for col, column in enumerate(columns):
            self.list.heading(f"#{col + 1}", text=column)
            self.list.column(
                f"#{col + 1}",
                minwidth=10,
                width=widths[col],
                anchor=tk.W if col == 0 else tk.CENTER,
            )
        self.list.grid(row=1, column=0, padx=5, sticky="NSEW")
        self.scrollbar = ttk.Scrollbar(
            self.top_frame, orient="vertical", command=self.list.yview
        )
        self.scrollbar.grid(row=1, column=1, sticky="NS")
        self.list.config(yscrollcommand=self.scrollbar.set)
        self.list.tag_configure(self.SEPARATOR_TAG, foreground="gray")

        # Bind events for list and entry
        self.list.bind("<Return>", self.execute_command)
        self.list.bind("<Double-Button-1>", self.execute_command)
        self.list.bind("<Down>", lambda _: self.move_in_list(1))
        self.list.bind("<Up>", lambda _: self.move_in_list(-1))
        self.list.bind("<Key>", self.handle_list_typing)

        self.entry.bind("<Down>", lambda _: self.move_in_list(1))
        self.entry.bind("<Up>", lambda _: self.move_in_list(-1))
        self.entry.bind("<Return>", self.execute_command)

        self.update_list()
        self.entry.focus()

    @classmethod
    def add_orphan_commands(cls) -> None:
        """Add orphan commands to command palette."""

        menubar_metadata().add_button_orphan(
            "Command Palette, Edit Shortcut", cls.orphan_wrapper("edit_command")
        )
        menubar_metadata().add_button_orphan(
            "Command Palette, Select Next", cls.orphan_wrapper("move_in_list", 1)
        )
        menubar_metadata().add_button_orphan(
            "Command Palette, Select Previous", cls.orphan_wrapper("move_in_list", -1)
        )

    @classmethod
    def store_recreate_menus_callback(cls, callback: Callable) -> None:
        """Store function to be called to recreate menus."""
        cls.recreate_menus_callback = callback

    def grab_focus(self) -> None:
        """Override grabbing focus to set focus to Entry field."""
        super().grab_focus()
        self.entry.focus()

    def update_list(self) -> None:
        """Update the command list based on search input."""

        search_text = self.search_var.get().lower().strip()

        def score_command(cmd: EntryMetadata) -> int:
            """Return how well search text matches this command."""
            label_lower = cmd.display_label().lower()
            menu_lower = cmd.display_parent_label().lower()
            if label_lower.startswith(search_text):
                score = RecentPlusEntry.PREFIXMATCH  # strong prefix match
            elif search_text in label_lower:
                score = RecentPlusEntry.SUBSTRMATCH  # weaker substring match
            elif menu_lower.startswith(search_text):
                score = RecentPlusEntry.MENUMATCH  # strong menu prefix
            else:  # fallback to fuzzy match
                score = int(
                    process.extractOne(search_text, [f"{menu_lower} {label_lower}"])[1]
                )
            return score

        def recent_key(recent_plus_entry: RecentPlusEntry) -> tuple[int, int, int, str]:
            """Sort based on recent/not, match score, recentness, then alphabetic."""
            score = score_command(recent_plus_entry.entry)
            # If recent, but not a direct match, pretend it's not recent
            if recent_plus_entry.recentness < RecentPlusEntry.SEPARATOR:
                recent_band = 0 if score >= RecentPlusEntry.MENUMATCH else 2
            elif recent_plus_entry.recentness == RecentPlusEntry.SEPARATOR:
                recent_band = 1
            else:
                recent_band = 2
            return (
                recent_band,
                -score,
                recent_plus_entry.recentness,
                recent_plus_entry.entry.display_label().lower(),
            )

        # Filtered commands have an int to store recentness (-10 for non-recent)
        self.filtered_entries = []

        recent_commands = preferences.get(PrefKey.COMMAND_PALETTE_HISTORY)

        # Add separator (recentness = -1)
        if recent_commands:
            self.filtered_entries.append(
                RecentPlusEntry(
                    RecentPlusEntry.SEPARATOR,
                    EntryMetadata(SEP_CHAR * 150, SEP_CHAR * 30, SEP_CHAR * 30),
                )
            )

        for cmd in self.commands:
            self.filtered_entries.append(
                RecentPlusEntry(RecentPlusEntry.NONRECENT, cmd)
            )

        # Set recentness for recent commands
        for recentness, (label, menu) in enumerate(recent_commands):
            for recent_plus_entry in self.filtered_entries:
                if (
                    recent_plus_entry.entry.label == label
                    and recent_plus_entry.entry.parent_label == menu
                ):
                    recent_plus_entry.recentness = recentness
                    break

        # Now sort commands by recentness, match score, and alphabetically
        self.filtered_entries.sort(key=recent_key)

        # Construct dialog list
        self.list.delete(*self.list.get_children())

        separator_hidden = False
        for idx, recent_plus_entry in enumerate(self.filtered_entries):
            entry = recent_plus_entry.entry
            sep = recent_plus_entry.recentness == RecentPlusEntry.SEPARATOR
            if sep and idx == 0:
                separator_hidden = True
                continue  # Don't put separator at top of list
            iid = self.list.insert(
                "",
                "end",
                values=(
                    entry.display_label(),
                    entry.display_shortcut(),
                    entry.display_parent_label(),
                ),
            )
            if sep:
                self.list.item(iid, tags=self.SEPARATOR_TAG, open=False)
        # If separator at top of list was suppressed, update filtered_entries to match
        if separator_hidden:
            del self.filtered_entries[0]

        if self.filtered_entries:
            self.list.select_and_focus_by_index(0)

    def edit_command(self) -> None:
        """Edit the selected command."""
        entry = self.get_selected_entry()
        if entry is None:
            return
        self.add_to_history(entry.label, entry.parent_label)
        self.edit_dialog = CommandEditDialog.show_dialog(command_dlg=self)
        self.edit_dialog.load(entry)

    def execute_command(self, event: Optional[tk.Event] = None) -> None:
        """Execute the selected command."""
        # Ignore if modifier key used: Shift, Ctrl, Cmd, Alt (platform-specific)
        bad_modifiers = 0x0001 | 0x0004 | 0x0008 | 0x0080 | 0x20000
        if event is not None and int(event.state) & bad_modifiers:
            return
        entry = self.get_selected_entry()
        if entry is None:
            return
        self.add_to_history(entry.label, entry.parent_label)
        command = entry.get_command()
        self.destroy()
        Busy.busy()  # In case it's a slow command
        command()
        Busy.unbusy()  # In case it's a slow command

    def get_selected_entry(self) -> Optional[EntryMetadata]:
        """Return EntryMetadata associated with selected entry in list (or None)."""
        selection = self.list.selection()
        if not selection:
            return None
        item = selection[0]
        if self.list.tag_has(self.SEPARATOR_TAG, item):
            return None
        return self.filtered_entries[self.list.index(item)].entry

    def focus_on_list(self, direction: int) -> None:
        """Move focus to the list and select the next/previous item.

        Args:
            direction: +1 to move down, -1 to move up.
        """
        self.list.focus_set()
        if self.filtered_entries:  # Select the next item in the list
            self.move_in_list(direction)

    def move_in_list(self, direction: int) -> str:
        """Move the selection in the list.

        Args:
            direction: +1 to move down, -1 to move up.
        """
        current_selection = self.list.selection()
        if current_selection:
            current_index = self.list.index(current_selection[0])
            new_index = current_index + direction
            if 0 <= new_index < len(self.filtered_entries):
                next_item = self.list.get_children()[new_index]
                # Skip over separator
                if self.list.tag_has(self.SEPARATOR_TAG, next_item):
                    next_item = self.list.get_children()[new_index + direction]
                self.list.select_and_focus_by_child(next_item)
            elif new_index < 0:
                # Moving up from first list element - focus in entry field
                self.entry.focus_set()
                self.entry.icursor(tk.END)
        return "break"

    def handle_list_typing(self, event: tk.Event) -> None:
        """Handle key press in the list to simulate typing in the Entry box."""
        current_text = self.search_var.get()
        # If (some) modifier keys pressed with character when typing in list,
        # don't add the char to the entry field:
        # Shift, Caps Lock, etc. are OK, but not Ctrl, Cmd, Alt (platform-specific)
        bad_modifiers = 0x0004 | 0x0008 | 0x0080 | 0x20000
        state = int(event.state)
        if event.keysym in ("BackSpace", "Delete"):
            self.search_var.set(current_text[:-1])
            self.update_list()  # Update the list based on the new search text
        elif event.char and event.char.isprintable() and not state & bad_modifiers:
            # If a proper char, add it to the entry
            self.search_var.set(current_text + event.char)
            self.update_list()  # Update the list based on the new search text

    def add_to_history(self, label: str, parent_label: str) -> None:
        """Store given entry in history list pref.

        Args:
            label: Label of entry to add to history.
            menu: Name of menu for entry to add to history.
        """
        history: list[list[str]] = preferences.get(PrefKey.COMMAND_PALETTE_HISTORY)
        try:
            history.remove([label, parent_label])
        except ValueError:
            pass  # OK if entry wasn't in list
        history.insert(0, [label, parent_label])
        preferences.set(PrefKey.COMMAND_PALETTE_HISTORY, history[: self.NUM_HISTORY])
        self.update_list()  # Update the list based on the new search text

    def on_destroy(self) -> None:
        if self.edit_dialog is not None and self.edit_dialog.winfo_exists():
            self.edit_dialog.destroy()
            self.edit_dialog = None
        return super().on_destroy()


class SurroundWithDialog(OkApplyCancelDialog):
    """Dialog for surrounding selection with strings."""

    manual_page = "Edit_Menu#Surround_Selection_With"

    def __init__(self) -> None:
        """Initialize Surround With dialog."""
        super().__init__("Surround With", resize_x=False, resize_y=False)

        ttk.Label(
            self.top_frame,
            text="Before",
        ).grid(row=0, column=0)
        ttk.Label(
            self.top_frame,
            text="After",
        ).grid(row=0, column=2)

        self.before_entry = Combobox(
            self.top_frame,
            PrefKey.SURROUND_WITH_BEFORE_HISTORY,
            textvariable=PersistentString(PrefKey.SURROUND_WITH_BEFORE),
        )
        self.before_entry.grid(row=1, column=0)
        ToolTip(self.before_entry, r'Use "\n" for newline')
        autofill_btn = ttk.Button(
            self.top_frame,
            text="⟹",
            command=self.autofill_after,
        )
        autofill_btn.grid(row=1, column=1, padx=5)
        ToolTip(autofill_btn, 'Autofill "After" entry field, e.g. <i lang="fr"> ⟹ </i>')
        self.after_entry = Combobox(
            self.top_frame,
            PrefKey.SURROUND_WITH_AFTER_HISTORY,
            textvariable=PersistentString(PrefKey.SURROUND_WITH_AFTER),
        )
        self.after_entry.grid(row=1, column=2)
        ToolTip(self.after_entry, r'Use "\n" for newline')

    @classmethod
    def add_orphan_commands(cls) -> None:
        """Add orphan commands to surround with dialog."""

        menubar_metadata().add_button_orphan(
            "Surround Selection With, Apply",
            cls.orphan_wrapper("do_apply_changes"),
        )

    @classmethod
    def do_apply_changes(cls) -> None:
        """Apply surrounding text based on most recent before/after text."""
        maintext().undo_block_begin()
        ranges = maintext().selected_ranges()
        if not ranges:
            ranges = [
                IndexRange(maintext().get_insert_index(), maintext().get_insert_index())
            ]
        end_mark = cls.get_dlg_name() + "endpoint"
        maintext().mark_set(end_mark, ranges[-1].end.index())
        before = preferences.get(PrefKey.SURROUND_WITH_BEFORE).replace(r"\n", "\n")
        after = preferences.get(PrefKey.SURROUND_WITH_AFTER).replace(r"\n", "\n")
        # Reversed so earlier change doesn't affect later indexes
        for a_range in reversed(ranges):
            maintext().insert(a_range.end.index(), after)
            maintext().insert(a_range.start.index(), before)
        # Position cursor at end of last selection so user can do Find Next to find the next match
        maintext().set_insert_index(maintext().rowcol(end_mark), focus=False)

    def apply_changes(self) -> bool:
        """Overridden method to apply surround text"""
        SurroundWithDialog.do_apply_changes()
        self.before_entry.add_to_history(preferences.get(PrefKey.SURROUND_WITH_BEFORE))
        self.after_entry.add_to_history(preferences.get(PrefKey.SURROUND_WITH_AFTER))
        return True  # Always successful

    def autofill_after(self) -> None:
        """Autofill the "after" entry field with a sensible guess."""
        pairs = {
            "<": ">",
            "<<": ">>",
            "[**": "]",
            "[** ": "]",
            "[": "]",
            "{": "}",
            "(": ")",
            '"': '"',
            "'": "'",
            "“": "”",
            "‘": "’",
        }

        before = preferences.get(PrefKey.SURROUND_WITH_BEFORE)

        # Tag with attributes, e.g. <tag attr="value"> => </tag>
        if m := re.match(r"<(\w+).*>$", before):
            after = f"</{m.group(1)}>"
        else:
            after = pairs.get(before, before)
        preferences.set(PrefKey.SURROUND_WITH_AFTER, after)


class UnicodeBlockDialog(ToplevelDialog):
    """A dialog that displays a block of Unicode characters, and allows
    the user to click on them to insert them into text window."""

    manual_page = "Tools_Menu#Unicode_Blocks"
    commonly_used_characters_name = "Commonly Used Characters"

    def __init__(self) -> None:
        """Initialize Unicode Block dialog."""

        super().__init__("Unicode Block")

        self.combobox = ttk.Combobox(
            self.top_frame,
            width=50,
        )
        self.combobox.set(preferences.get(PrefKey.UNICODE_BLOCK))
        self.combobox.grid(
            column=0, row=0, sticky="NSW", padx=5, pady=(5, 0), columnspan=2
        )
        block_list = []
        for name, (beg, end, show) in _unicode_blocks.items():
            if show:
                block_list.append(f"{name}   ({beg:04X}–{end:04X})")
        block_list.sort()
        block_list.insert(0, UnicodeBlockDialog.commonly_used_characters_name)
        self.combobox["values"] = block_list
        self.combobox["state"] = "readonly"
        self.combobox.bind("<<ComboboxSelected>>", lambda _e: self.block_selected())
        self.top_frame.rowconfigure(0, weight=0)
        self.top_frame.rowconfigure(1, weight=1)
        self.chars_frame = ScrollableFrame(self.top_frame)
        self.chars_frame.grid(
            column=0, row=1, sticky="NSEW", padx=5, pady=5, columnspan=2
        )
        big_frame = ttk.Frame(self.top_frame, borderwidth=3, relief=tk.SUNKEN)
        big_frame.grid(row=2, column=0, sticky="NSW", padx=5, pady=5)
        self.bigchar_var = tk.StringVar()
        big_font = font.nametofont(maintext().cget("font"))
        big_font = big_font.copy()
        big_font.configure(size=24)
        ttk.Label(
            big_frame,
            textvariable=self.bigchar_var,
            font=big_font,
            width=2,
            anchor=tk.CENTER,
        ).grid(row=0, column=0, sticky="NSEW", padx=(2, 0), pady=(0, 2))
        self.top_frame.columnconfigure(0, weight=0)
        self.top_frame.columnconfigure(1, weight=1)
        self.charname_var = tk.StringVar()
        ttk.Label(self.top_frame, textvariable=self.charname_var).grid(
            row=2, column=1, sticky="NSW", padx=5, pady=5
        )

        self.button_list: list[ttk.Label] = []
        self.block_selected(update_pref=False)

    @classmethod
    def show_unicode_dialog(cls) -> None:
        """Show dialog in Unicode block mode."""
        dlg = UnicodeBlockDialog.show_dialog()
        dlg.combobox.set(preferences.get(PrefKey.UNICODE_BLOCK))
        dlg.block_selected(update_pref=False)

    @classmethod
    def show_common_dialog(cls) -> None:
        """Show dialog in Commonly Used Characters mode."""
        dlg = UnicodeBlockDialog.show_dialog()
        dlg.combobox.set(UnicodeBlockDialog.commonly_used_characters_name)
        dlg.block_selected(update_pref=False)

    def block_selected(self, update_pref: bool = True) -> None:
        """Called when a Unicode block is selected.

        Args:
            update_pref: Set False if pref should not be updated.
        """
        for btn in self.button_list:
            if btn.winfo_exists():
                btn.destroy()
        self.button_list.clear()
        self.chars_frame.reset_scroll()

        def add_button(count: int, char: str) -> None:
            """Add a button to the Unicode block dialog.

            Args:
                count: Count of buttons added, used to determine row/column.
                char: Character to use as label for button.
            """
            btn = ttk.Label(
                self.chars_frame,
                text=char,
                width=2,
                borderwidth=2,
                relief=tk.SOLID,
                anchor=tk.CENTER,
                font=maintext().font,
            )

            def press(event: tk.Event) -> None:
                event.widget["relief"] = tk.SUNKEN

            def release(event: tk.Event, char: str) -> None:
                event.widget["relief"] = tk.RAISED
                insert_in_focus_widget(char)

            def show_name(wgt: tk.Label) -> None:
                char = str(wgt["text"])
                name, new = unicode_char_to_name(char)
                if name:
                    name = ": " + name
                warning_flag = "⚠\ufe0f" if new else ""
                self.charname_var.set(f"{warning_flag}U+{ord(char):04x}{name}")
                self.bigchar_var.set(char)

            def clear_name() -> None:
                self.charname_var.set("")
                self.bigchar_var.set("")

            def enter(event: tk.Event) -> None:
                event.widget["relief"] = tk.RAISED
                show_name(event.widget)

            def leave(event: tk.Event) -> None:
                relief = str(event.widget["relief"])
                if relief == tk.RAISED:
                    event.widget["relief"] = tk.SOLID
                clear_name()

            btn.bind("<ButtonPress-1>", press)
            btn.bind("<ButtonRelease-1>", lambda e: release(e, char))
            btn.bind("<Enter>", enter)
            btn.bind("<Leave>", leave)
            btn.grid(column=count % 16, row=int(count / 16), sticky="NSEW")
            self.button_list.append(btn)

        if update_pref:
            preferences.set(PrefKey.UNICODE_BLOCK, self.combobox.get())
        block_name = re.sub(r" *\(.*", "", self.combobox.get())
        if block_name == UnicodeBlockDialog.commonly_used_characters_name:
            for count, char in enumerate(_common_characters):
                add_button(count, char)
        else:
            block_range = _unicode_blocks[block_name]
            for count, c_ord in enumerate(range(block_range[0], block_range[1] + 1)):
                add_button(count, chr(c_ord))


class UnicodeSearchDialog(ToplevelDialog):
    """A dialog that allows user to search for Unicode characters,
    given partial name match or Unicode ordinal, and allows
    the user to insert it into text window."""

    manual_page = "Tools_Menu#Unicode_Search/Entry"
    CHAR_COL_ID = "#1"
    CHAR_COL_HEAD = "Char"
    CHAR_COL_WIDTH = 50
    CODEPOINT_COL_ID = "#2"
    CODEPOINT_COL_HEAD = "Code Point"
    CODEPOINT_COL_WIDTH = 80
    NAME_COL_ID = "#3"
    NAME_COL_HEAD = "Name"
    NAME_COL_WIDTH = 250
    BLOCK_COL_ID = "#4"
    BLOCK_COL_HEAD = "Block"
    BLOCK_COL_WIDTH = 180

    def __init__(self) -> None:
        """Initialize Unicode Search dialog."""

        super().__init__("Unicode Search")

        search_frame = ttk.Frame(self.top_frame)
        search_frame.grid(column=0, row=0, sticky="NSEW")
        search_frame.columnconfigure(0, weight=1)
        search_frame.columnconfigure(1, weight=0)
        self.search = Combobox(
            search_frame,
            PrefKey.UNICODE_SEARCH_HISTORY,
            width=50,
            font=maintext().font,
        )
        self.search.grid(column=0, row=0, sticky="NSEW", padx=5, pady=(5, 0))
        self.search.focus()
        ToolTip(
            self.search,
            "\n".join(
                [
                    "Type words from character name to match against,",
                    "or hex codepoint (optionally preceded by 'U+' or 'X'),",
                    "or type/paste a single character to search for",
                ]
            ),
        )

        search_btn = ttk.Button(
            search_frame,
            text="Search",
            default="active",
            command=lambda: self.find_matches(self.search.get()),
        )
        search_btn.grid(column=1, row=0, sticky="NSEW")
        self.bind("<Return>", lambda _: search_btn.invoke())
        self.search.bind("<<ComboboxSelected>>", lambda _e: search_btn.invoke())

        self.top_frame.rowconfigure(0, weight=0)
        self.top_frame.rowconfigure(1, weight=1)

        columns = (
            UnicodeSearchDialog.CHAR_COL_HEAD,
            UnicodeSearchDialog.CODEPOINT_COL_HEAD,
            UnicodeSearchDialog.NAME_COL_HEAD,
            UnicodeSearchDialog.BLOCK_COL_HEAD,
        )
        widths = (
            UnicodeSearchDialog.CHAR_COL_WIDTH,
            UnicodeSearchDialog.CODEPOINT_COL_WIDTH,
            UnicodeSearchDialog.NAME_COL_WIDTH,
            UnicodeSearchDialog.BLOCK_COL_WIDTH,
        )
        self.list = TreeviewList(
            self.top_frame,
            columns=columns,
            height=15,
        )
        ToolTip(
            self.list,
            "\n".join(
                [
                    f"Click in {UnicodeSearchDialog.CHAR_COL_HEAD},  {UnicodeSearchDialog.CODEPOINT_COL_HEAD} or {UnicodeSearchDialog.NAME_COL_HEAD} column (or press Space or Return) to insert character",
                    f"Click in {UnicodeSearchDialog.BLOCK_COL_HEAD} column (or press Shift+Space or Shift+Return) to open Unicode Block dialog",
                    "(⚠\ufe0f before a character's name means it was added more recently - use with caution)",
                ]
            ),
            use_pointer_pos=True,
        )
        for col, column in enumerate(columns):
            col_id = f"#{col + 1}"
            anchor: Literal["center", "w"] = (
                tk.CENTER if col_id == UnicodeSearchDialog.CHAR_COL_ID else tk.W
            )
            self.list.column(
                col_id,
                minwidth=20,
                width=widths[col],
                stretch=(col_id == UnicodeSearchDialog.NAME_COL_ID),
                anchor=anchor,
            )
            self.list.heading(col_id, text=column, anchor=anchor)
        self.list.grid(row=1, column=0, sticky=tk.NSEW, pady=(5, 0))

        self.scrollbar = ttk.Scrollbar(
            self.top_frame, orient=tk.VERTICAL, command=self.list.yview
        )
        self.list.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid(row=1, column=1, sticky=tk.NS)
        mouse_bind(self.list, "1", self.item_clicked)
        self.list.bind("<Return>", self.insert_character)
        self.list.bind("<space>", self.insert_character)
        self.list.bind("<Shift-Return>", self.open_block)
        self.list.bind("<Shift-space>", self.open_block)

        char = maintext().selected_text()
        if len(char) == 1 and not char.isspace():
            self.search.delete(0, tk.END)
            self.search.insert(0, char)
            search_btn.invoke()

    def find_matches(self, string: str) -> None:
        """Find & display Unicode characters that match all criteria (words) in the given string.

        Args:
            string: String containing words that must appear in the characters' names. If no match
                    is found, check if string is a hex number which is the codepoint of a character.
        """
        # Clear existing display of chars
        children = self.list.get_children()
        for child in children:
            self.list.delete(child)

        # Split user string into words
        match_words = [x.lower() for x in string.split(" ") if x]
        if len(match_words) > 0:
            self.search.add_to_history(string)

        # Check every Unicode character to see if its name contains all the given words
        # (including hyphenated, e.g. BREAK will match NO-BREAK, but not NON-BREAKING)
        found = False
        if len(match_words) > 0:
            for ordinal in range(0, sys.maxunicode + 1):
                char = chr(ordinal)
                name, new = unicode_char_to_name(char)
                name_list = name.lower().split(" ")
                hyphen_parts: list[str] = []
                for word in name_list:
                    if "-" in word:
                        hyphen_parts += word.split("-")
                name_list += hyphen_parts
                if name and all(word in name_list for word in match_words):
                    self.add_row(char, new)
                    found = True

        if not found:  # Maybe string was a hex codepoint?
            hex_string = re.sub(r"^(U\+|0?X)", "", string.strip(), flags=re.IGNORECASE)
            char = ""
            try:
                char = chr(int(hex_string, 16))
            except (OverflowError, ValueError):
                pass
            if char:
                name, new = unicode_char_to_name(char)
                if name:
                    self.add_row(char, new)
                    found = True

        # Maybe string was a single character?
        # Carefully strip spaces, so that a single space still works
        if not found and len(string) >= 1:
            string = string.strip(" ")
            if len(string) == 0:
                string = " "  # String was all spaces
            if len(string) == 1:
                name, new = unicode_char_to_name(string)
                if name:
                    self.add_row(string, new)
                    found = True

        if found:
            self.list.select_and_focus_by_index(0)
        else:
            sound_bell()

    def add_row(self, char: str, new: bool) -> None:
        """Add a row to the Unicode Search dialog.

        Args:
            count: Row to add.
            char: Character to display in row.
            new: True if character was added to unicode since version 3.2 (March 2002)
        """
        ordinal = ord(char)
        block_name = ""
        warning_flag = "⚠\ufe0f" if new else ""
        # Find block name
        for block, (beg, end, _) in _unicode_blocks.items():
            if beg <= ordinal <= end:
                block_name = block
                break
        # Add entry to Treeview
        entry = (
            char,
            f"U+{ord(char):04x}",
            warning_flag + unicodedata.name(char),
            block_name,
        )
        self.list.insert("", tk.END, values=entry)

    def item_clicked(self, event: tk.Event) -> None:
        """Called when Unicode search item is clicked.

        If click is in char, codepoint or name column, then insert character.
        If in block column, open the block dialog.

        Args:
            event: Event containing location of mouse click
        """
        row_id, col_id = self.list.identify_rowcol(event)
        row = self.list.set(row_id)
        if not row:  # Heading clicked
            return

        if col_id in (
            UnicodeSearchDialog.CHAR_COL_ID,
            UnicodeSearchDialog.CODEPOINT_COL_ID,
            UnicodeSearchDialog.NAME_COL_ID,
        ):
            insert_in_focus_widget(row[UnicodeSearchDialog.CHAR_COL_HEAD])
        elif col_id == UnicodeSearchDialog.BLOCK_COL_ID:
            block = row[UnicodeSearchDialog.BLOCK_COL_HEAD]
            if not block:
                return
            dlg = UnicodeBlockDialog.show_dialog()
            dlg.combobox.set(block)
            dlg.block_selected()

    def insert_character(self, _: tk.Event) -> None:
        """Insert character when Return pressed in list."""
        row_id = self.list.focus()
        if not row_id:
            return
        row = self.list.set(row_id)
        insert_in_focus_widget(row[UnicodeSearchDialog.CHAR_COL_HEAD])

    def open_block(self, _: tk.Event) -> None:
        """Open Unicode block when Shift-Return pressed in list."""
        row_id = self.list.focus()
        if not row_id:
            return
        row = self.list.set(row_id)
        block = row[UnicodeSearchDialog.BLOCK_COL_HEAD]
        if not block:
            return
        dlg = UnicodeBlockDialog.show_dialog()
        dlg.combobox.set(block)
        dlg.block_selected()


def unicode_char_to_name(char: str) -> tuple[str, bool]:
    """Convert char to Unicode name, and note if it is "new".

    Args:
        char: Character to convert.

    Returns:
        Tuple containing name of character (empty if no name),
        and bool flagging if character is new (Unicode version > 3.2).
    """
    new = False
    try:
        name = unicodedata.name(char)
        try:
            unicodedata.ucd_3_2_0.name(char)
        except ValueError:
            new = True
    except ValueError:
        name = ""
    return name, new


# Somewhat arbitrarily, certain Unicode blocks are not displayed in the
# dropdown menu, roughly matching the GG1 list, and trying to
# balance usefulness with excessive number of blocks to choose from.
# List of blocks taken from https://unicode.org/Public/UNIDATA/Blocks.txt with header
#     Blocks-16.0.0.txt
#     Date: 2024-02-02
# Start point of Basic Latin and Latin-1 Supplement adjusted to avoid unprintables
_unicode_blocks: dict[str, tuple[int, int, bool]] = {
    "Basic Latin": (0x0020, 0x007E, True),
    "Latin-1 Supplement": (0x00A0, 0x00FF, True),
    "Latin Extended-A": (0x0100, 0x017F, True),
    "Latin Extended-B": (0x0180, 0x024F, True),
    "IPA Extensions": (0x0250, 0x02AF, True),
    "Spacing Modifier Letters": (0x02B0, 0x02FF, True),
    "Combining Diacritical Marks": (0x0300, 0x036F, True),
    "Greek and Coptic": (0x0370, 0x03FF, True),
    "Cyrillic": (0x0400, 0x04FF, True),
    "Cyrillic Supplement": (0x0500, 0x052F, True),
    "Armenian": (0x0530, 0x058F, True),
    "Hebrew": (0x0590, 0x05FF, True),
    "Arabic": (0x0600, 0x06FF, True),
    "Syriac": (0x0700, 0x074F, True),
    "Arabic Supplement": (0x0750, 0x077F, False),
    "Thaana": (0x0780, 0x07BF, True),
    "NKo": (0x07C0, 0x07FF, False),
    "Samaritan": (0x0800, 0x083F, False),
    "Mandaic": (0x0840, 0x085F, False),
    "Syriac Supplement": (0x0860, 0x086F, False),
    "Arabic Extended-B": (0x0870, 0x089F, False),
    "Arabic Extended-A": (0x08A0, 0x08FF, False),
    "Devanagari": (0x0900, 0x097F, True),
    "Bengali": (0x0980, 0x09FF, True),
    "Gurmukhi": (0x0A00, 0x0A7F, True),
    "Gujarati": (0x0A80, 0x0AFF, True),
    "Oriya": (0x0B00, 0x0B7F, True),
    "Tamil": (0x0B80, 0x0BFF, True),
    "Telugu": (0x0C00, 0x0C7F, True),
    "Kannada": (0x0C80, 0x0CFF, True),
    "Malayalam": (0x0D00, 0x0D7F, True),
    "Sinhala": (0x0D80, 0x0DFF, True),
    "Thai": (0x0E00, 0x0E7F, True),
    "Lao": (0x0E80, 0x0EFF, True),
    "Tibetan": (0x0F00, 0x0FFF, False),
    "Myanmar": (0x1000, 0x109F, True),
    "Georgian": (0x10A0, 0x10FF, True),
    "Hangul Jamo": (0x1100, 0x11FF, True),
    "Ethiopic": (0x1200, 0x137F, True),
    "Ethiopic Supplement": (0x1380, 0x139F, False),
    "Cherokee": (0x13A0, 0x13FF, True),
    "Unified Canadian Aboriginal Syllabics": (0x1400, 0x167F, True),
    "Ogham": (0x1680, 0x169F, True),
    "Runic": (0x16A0, 0x16FF, True),
    "Tagalog": (0x1700, 0x171F, True),
    "Hanunoo": (0x1720, 0x173F, False),
    "Buhid": (0x1740, 0x175F, True),
    "Tagbanwa": (0x1760, 0x177F, False),
    "Khmer": (0x1780, 0x17FF, False),
    "Mongolian": (0x1800, 0x18AF, True),
    "Unified Canadian Aboriginal Syllabics Extended": (0x18B0, 0x18FF, False),
    "Limbu": (0x1900, 0x194F, False),
    "Tai Le": (0x1950, 0x197F, False),
    "New Tai Lue": (0x1980, 0x19DF, False),
    "Khmer Symbols": (0x19E0, 0x19FF, False),
    "Buginese": (0x1A00, 0x1A1F, False),
    "Tai Tham": (0x1A20, 0x1AAF, False),
    "Combining Diacritical Marks Extended": (0x1AB0, 0x1AFF, False),
    "Balinese": (0x1B00, 0x1B7F, False),
    "Sundanese": (0x1B80, 0x1BBF, False),
    "Batak": (0x1BC0, 0x1BFF, False),
    "Lepcha": (0x1C00, 0x1C4F, False),
    "Ol Chiki": (0x1C50, 0x1C7F, False),
    "Cyrillic Extended-C": (0x1C80, 0x1C8F, False),
    "Georgian Extended": (0x1C90, 0x1CBF, False),
    "Sundanese Supplement": (0x1CC0, 0x1CCF, False),
    "Vedic Extensions": (0x1CD0, 0x1CFF, False),
    "Phonetic Extensions": (0x1D00, 0x1D7F, True),
    "Phonetic Extensions Supplement": (0x1D80, 0x1DBF, False),
    "Combining Diacritical Marks Supplement": (0x1DC0, 0x1DFF, False),
    "Latin Extended Additional": (0x1E00, 0x1EFF, True),
    "Greek Extended": (0x1F00, 0x1FFF, True),
    "General Punctuation": (0x2000, 0x206F, True),
    "Superscripts and Subscripts": (0x2070, 0x209F, True),
    "Currency Symbols": (0x20A0, 0x20CF, True),
    "Combining Diacritical Marks for Symbols": (0x20D0, 0x20FF, True),
    "Letterlike Symbols": (0x2100, 0x214F, True),
    "Number Forms": (0x2150, 0x218F, True),
    "Arrows": (0x2190, 0x21FF, True),
    "Mathematical Operators": (0x2200, 0x22FF, True),
    "Miscellaneous Technical": (0x2300, 0x23FF, True),
    "Control Pictures": (0x2400, 0x243F, True),
    "Optical Character Recognition": (0x2440, 0x245F, True),
    "Enclosed Alphanumerics": (0x2460, 0x24FF, True),
    "Box Drawing": (0x2500, 0x257F, True),
    "Block Elements": (0x2580, 0x259F, True),
    "Geometric Shapes": (0x25A0, 0x25FF, True),
    "Miscellaneous Symbols": (0x2600, 0x26FF, True),
    "Dingbats": (0x2700, 0x27BF, True),
    "Miscellaneous Mathematical Symbols-A": (0x27C0, 0x27EF, True),
    "Supplemental Arrows-A": (0x27F0, 0x27FF, True),
    "Braille Patterns": (0x2800, 0x28FF, True),
    "Supplemental Arrows-B": (0x2900, 0x297F, True),
    "Miscellaneous Mathematical Symbols-B": (0x2980, 0x29FF, True),
    "Supplemental Mathematical Operators": (0x2A00, 0x2AFF, True),
    "Miscellaneous Symbols and Arrows": (0x2B00, 0x2BFF, True),
    "Glagolitic": (0x2C00, 0x2C5F, False),
    "Latin Extended-C": (0x2C60, 0x2C7F, False),
    "Coptic": (0x2C80, 0x2CFF, False),
    "Georgian Supplement": (0x2D00, 0x2D2F, False),
    "Tifinagh": (0x2D30, 0x2D7F, False),
    "Ethiopic Extended": (0x2D80, 0x2DDF, False),
    "Cyrillic Extended-A": (0x2DE0, 0x2DFF, False),
    "Supplemental Punctuation": (0x2E00, 0x2E7F, False),
    "CJK Radicals Supplement": (0x2E80, 0x2EFF, False),
    "Kangxi Radicals": (0x2F00, 0x2FDF, False),
    "Ideographic Description Characters": (0x2FF0, 0x2FFF, False),
    "CJK Symbols and Punctuation": (0x3000, 0x303F, False),
    "Hiragana": (0x3040, 0x309F, False),
    "Katakana": (0x30A0, 0x30FF, False),
    "Bopomofo": (0x3100, 0x312F, False),
    "Hangul Compatibility Jamo": (0x3130, 0x318F, False),
    "Kanbun": (0x3190, 0x319F, False),
    "Bopomofo Extended": (0x31A0, 0x31BF, False),
    "CJK Strokes": (0x31C0, 0x31EF, False),
    "Katakana Phonetic Extensions": (0x31F0, 0x31FF, False),
    "Enclosed CJK Letters and Months": (0x3200, 0x32FF, False),
    "CJK Compatibility": (0x3300, 0x33FF, False),
    "CJK Unified Ideographs Extension A": (0x3400, 0x4DBF, False),
    "Yijing Hexagram Symbols": (0x4DC0, 0x4DFF, False),
    "CJK Unified Ideographs": (0x4E00, 0x9FFF, False),
    "Yi Syllables": (0xA000, 0xA48F, False),
    "Yi Radicals": (0xA490, 0xA4CF, False),
    "Lisu": (0xA4D0, 0xA4FF, False),
    "Vai": (0xA500, 0xA63F, False),
    "Cyrillic Extended-B": (0xA640, 0xA69F, False),
    "Bamum": (0xA6A0, 0xA6FF, False),
    "Modifier Tone Letters": (0xA700, 0xA71F, False),
    "Latin Extended-D": (0xA720, 0xA7FF, False),
    "Syloti Nagri": (0xA800, 0xA82F, False),
    "Common Indic Number Forms": (0xA830, 0xA83F, False),
    "Phags-pa": (0xA840, 0xA87F, False),
    "Saurashtra": (0xA880, 0xA8DF, False),
    "Devanagari Extended": (0xA8E0, 0xA8FF, False),
    "Kayah Li": (0xA900, 0xA92F, False),
    "Rejang": (0xA930, 0xA95F, False),
    "Hangul Jamo Extended-A": (0xA960, 0xA97F, False),
    "Javanese": (0xA980, 0xA9DF, False),
    "Myanmar Extended-B": (0xA9E0, 0xA9FF, False),
    "Cham": (0xAA00, 0xAA5F, False),
    "Myanmar Extended-A": (0xAA60, 0xAA7F, False),
    "Tai Viet": (0xAA80, 0xAADF, False),
    "Meetei Mayek Extensions": (0xAAE0, 0xAAFF, False),
    "Ethiopic Extended-A": (0xAB00, 0xAB2F, False),
    "Latin Extended-E": (0xAB30, 0xAB6F, False),
    "Cherokee Supplement": (0xAB70, 0xABBF, False),
    "Meetei Mayek": (0xABC0, 0xABFF, False),
    "Hangul Syllables": (0xAC00, 0xD7AF, False),
    "Hangul Jamo Extended-B": (0xD7B0, 0xD7FF, False),
    "High Surrogates": (0xD800, 0xDB7F, False),
    "High Private Use Surrogates": (0xDB80, 0xDBFF, False),
    "Low Surrogates": (0xDC00, 0xDFFF, False),
    "Private Use Area": (0xE000, 0xF8FF, False),
    "CJK Compatibility Ideographs": (0xF900, 0xFAFF, False),
    "Alphabetic Presentation Forms": (0xFB00, 0xFB4F, True),
    "Arabic Presentation Forms-A": (0xFB50, 0xFDFF, True),
    "Variation Selectors": (0xFE00, 0xFE0F, True),
    "Vertical Forms": (0xFE10, 0xFE1F, False),
    "Combining Half Marks": (0xFE20, 0xFE2F, True),
    "CJK Compatibility Forms": (0xFE30, 0xFE4F, False),
    "Small Form Variants": (0xFE50, 0xFE6F, True),
    "Arabic Presentation Forms-B": (0xFE70, 0xFEFF, True),
    "Halfwidth and Fullwidth Forms": (0xFF00, 0xFFEF, True),
    "Specials": (0xFFF0, 0xFFFF, False),
    "Linear B Syllabary": (0x10000, 0x1007F, False),
    "Linear B Ideograms": (0x10080, 0x100FF, False),
    "Aegean Numbers": (0x10100, 0x1013F, False),
    "Ancient Greek Numbers": (0x10140, 0x1018F, False),
    "Ancient Symbols": (0x10190, 0x101CF, False),
    "Phaistos Disc": (0x101D0, 0x101FF, False),
    "Lycian": (0x10280, 0x1029F, False),
    "Carian": (0x102A0, 0x102DF, False),
    "Coptic Epact Numbers": (0x102E0, 0x102FF, False),
    "Old Italic": (0x10300, 0x1032F, False),
    "Gothic": (0x10330, 0x1034F, False),
    "Old Permic": (0x10350, 0x1037F, False),
    "Ugaritic": (0x10380, 0x1039F, False),
    "Old Persian": (0x103A0, 0x103DF, False),
    "Deseret": (0x10400, 0x1044F, False),
    "Shavian": (0x10450, 0x1047F, False),
    "Osmanya": (0x10480, 0x104AF, False),
    "Osage": (0x104B0, 0x104FF, False),
    "Elbasan": (0x10500, 0x1052F, False),
    "Caucasian Albanian": (0x10530, 0x1056F, False),
    "Vithkuqi": (0x10570, 0x105BF, False),
    "Todhri": (0x105C0, 0x105FF, False),
    "Linear A": (0x10600, 0x1077F, False),
    "Latin Extended-F": (0x10780, 0x107BF, False),
    "Cypriot Syllabary": (0x10800, 0x1083F, False),
    "Imperial Aramaic": (0x10840, 0x1085F, False),
    "Palmyrene": (0x10860, 0x1087F, False),
    "Nabataean": (0x10880, 0x108AF, False),
    "Hatran": (0x108E0, 0x108FF, False),
    "Phoenician": (0x10900, 0x1091F, False),
    "Lydian": (0x10920, 0x1093F, False),
    "Meroitic Hieroglyphs": (0x10980, 0x1099F, False),
    "Meroitic Cursive": (0x109A0, 0x109FF, False),
    "Kharoshthi": (0x10A00, 0x10A5F, False),
    "Old South Arabian": (0x10A60, 0x10A7F, False),
    "Old North Arabian": (0x10A80, 0x10A9F, False),
    "Manichaean": (0x10AC0, 0x10AFF, False),
    "Avestan": (0x10B00, 0x10B3F, False),
    "Inscriptional Parthian": (0x10B40, 0x10B5F, False),
    "Inscriptional Pahlavi": (0x10B60, 0x10B7F, False),
    "Psalter Pahlavi": (0x10B80, 0x10BAF, False),
    "Old Turkic": (0x10C00, 0x10C4F, False),
    "Old Hungarian": (0x10C80, 0x10CFF, False),
    "Hanifi Rohingya": (0x10D00, 0x10D3F, False),
    "Garay": (0x10D40, 0x10D8F, False),
    "Rumi Numeral Symbols": (0x10E60, 0x10E7F, False),
    "Yezidi": (0x10E80, 0x10EBF, False),
    "Arabic Extended-C": (0x10EC0, 0x10EFF, False),
    "Old Sogdian": (0x10F00, 0x10F2F, False),
    "Sogdian": (0x10F30, 0x10F6F, False),
    "Old Uyghur": (0x10F70, 0x10FAF, False),
    "Chorasmian": (0x10FB0, 0x10FDF, False),
    "Elymaic": (0x10FE0, 0x10FFF, False),
    "Brahmi": (0x11000, 0x1107F, False),
    "Kaithi": (0x11080, 0x110CF, False),
    "Sora Sompeng": (0x110D0, 0x110FF, False),
    "Chakma": (0x11100, 0x1114F, False),
    "Mahajani": (0x11150, 0x1117F, False),
    "Sharada": (0x11180, 0x111DF, False),
    "Sinhala Archaic Numbers": (0x111E0, 0x111FF, False),
    "Khojki": (0x11200, 0x1124F, False),
    "Multani": (0x11280, 0x112AF, False),
    "Khudawadi": (0x112B0, 0x112FF, False),
    "Grantha": (0x11300, 0x1137F, False),
    "Tulu-Tigalari": (0x11380, 0x113FF, False),
    "Newa": (0x11400, 0x1147F, False),
    "Tirhuta": (0x11480, 0x114DF, False),
    "Siddham": (0x11580, 0x115FF, False),
    "Modi": (0x11600, 0x1165F, False),
    "Mongolian Supplement": (0x11660, 0x1167F, False),
    "Takri": (0x11680, 0x116CF, False),
    "Myanmar Extended-C": (0x116D0, 0x116FF, False),
    "Ahom": (0x11700, 0x1174F, False),
    "Dogra": (0x11800, 0x1184F, False),
    "Warang Citi": (0x118A0, 0x118FF, False),
    "Dives Akuru": (0x11900, 0x1195F, False),
    "Nandinagari": (0x119A0, 0x119FF, False),
    "Zanabazar Square": (0x11A00, 0x11A4F, False),
    "Soyombo": (0x11A50, 0x11AAF, False),
    "Unified Canadian Aboriginal Syllabics Extended-A": (0x11AB0, 0x11ABF, False),
    "Pau Cin Hau": (0x11AC0, 0x11AFF, False),
    "Devanagari Extended-A": (0x11B00, 0x11B5F, False),
    "Sunuwar": (0x11BC0, 0x11BFF, False),
    "Bhaiksuki": (0x11C00, 0x11C6F, False),
    "Marchen": (0x11C70, 0x11CBF, False),
    "Masaram Gondi": (0x11D00, 0x11D5F, False),
    "Gunjala Gondi": (0x11D60, 0x11DAF, False),
    "Makasar": (0x11EE0, 0x11EFF, False),
    "Kawi": (0x11F00, 0x11F5F, False),
    "Lisu Supplement": (0x11FB0, 0x11FBF, False),
    "Tamil Supplement": (0x11FC0, 0x11FFF, False),
    "Cuneiform": (0x12000, 0x123FF, False),
    "Cuneiform Numbers and Punctuation": (0x12400, 0x1247F, False),
    "Early Dynastic Cuneiform": (0x12480, 0x1254F, False),
    "Cypro-Minoan": (0x12F90, 0x12FFF, False),
    "Egyptian Hieroglyphs": (0x13000, 0x1342F, False),
    "Egyptian Hieroglyph Format Controls": (0x13430, 0x1345F, False),
    "Egyptian Hieroglyphs Extended-A": (0x13460, 0x143FF, False),
    "Anatolian Hieroglyphs": (0x14400, 0x1467F, False),
    "Gurung Khema": (0x16100, 0x1613F, False),
    "Bamum Supplement": (0x16800, 0x16A3F, False),
    "Mro": (0x16A40, 0x16A6F, False),
    "Tangsa": (0x16A70, 0x16ACF, False),
    "Bassa Vah": (0x16AD0, 0x16AFF, False),
    "Pahawh Hmong": (0x16B00, 0x16B8F, False),
    "Kirat Rai": (0x16D40, 0x16D7F, False),
    "Medefaidrin": (0x16E40, 0x16E9F, False),
    "Miao": (0x16F00, 0x16F9F, False),
    "Ideographic Symbols and Punctuation": (0x16FE0, 0x16FFF, False),
    "Tangut": (0x17000, 0x187FF, False),
    "Tangut Components": (0x18800, 0x18AFF, False),
    "Khitan Small Script": (0x18B00, 0x18CFF, False),
    "Tangut Supplement": (0x18D00, 0x18D7F, False),
    "Kana Extended-B": (0x1AFF0, 0x1AFFF, False),
    "Kana Supplement": (0x1B000, 0x1B0FF, False),
    "Kana Extended-A": (0x1B100, 0x1B12F, False),
    "Small Kana Extension": (0x1B130, 0x1B16F, False),
    "Nushu": (0x1B170, 0x1B2FF, False),
    "Duployan": (0x1BC00, 0x1BC9F, False),
    "Shorthand Format Controls": (0x1BCA0, 0x1BCAF, False),
    "Symbols for Legacy Computing Supplement": (0x1CC00, 0x1CEBF, False),
    "Znamenny Musical Notation": (0x1CF00, 0x1CFCF, False),
    "Byzantine Musical Symbols": (0x1D000, 0x1D0FF, False),
    "Musical Symbols": (0x1D100, 0x1D1FF, False),
    "Ancient Greek Musical Notation": (0x1D200, 0x1D24F, False),
    "Kaktovik Numerals": (0x1D2C0, 0x1D2DF, False),
    "Mayan Numerals": (0x1D2E0, 0x1D2FF, False),
    "Tai Xuan Jing Symbols": (0x1D300, 0x1D35F, False),
    "Counting Rod Numerals": (0x1D360, 0x1D37F, False),
    "Mathematical Alphanumeric Symbols": (0x1D400, 0x1D7FF, False),
    "Sutton SignWriting": (0x1D800, 0x1DAAF, False),
    "Latin Extended-G": (0x1DF00, 0x1DFFF, False),
    "Glagolitic Supplement": (0x1E000, 0x1E02F, False),
    "Cyrillic Extended-D": (0x1E030, 0x1E08F, False),
    "Nyiakeng Puachue Hmong": (0x1E100, 0x1E14F, False),
    "Toto": (0x1E290, 0x1E2BF, False),
    "Wancho": (0x1E2C0, 0x1E2FF, False),
    "Nag Mundari": (0x1E4D0, 0x1E4FF, False),
    "Ol Onal": (0x1E5D0, 0x1E5FF, False),
    "Ethiopic Extended-B": (0x1E7E0, 0x1E7FF, False),
    "Mende Kikakui": (0x1E800, 0x1E8DF, False),
    "Adlam": (0x1E900, 0x1E95F, False),
    "Indic Siyaq Numbers": (0x1EC70, 0x1ECBF, False),
    "Ottoman Siyaq Numbers": (0x1ED00, 0x1ED4F, False),
    "Arabic Mathematical Alphabetic Symbols": (0x1EE00, 0x1EEFF, False),
    "Mahjong Tiles": (0x1F000, 0x1F02F, False),
    "Domino Tiles": (0x1F030, 0x1F09F, False),
    "Playing Cards": (0x1F0A0, 0x1F0FF, False),
    "Enclosed Alphanumeric Supplement": (0x1F100, 0x1F1FF, False),
    "Enclosed Ideographic Supplement": (0x1F200, 0x1F2FF, False),
    "Miscellaneous Symbols and Pictographs": (0x1F300, 0x1F5FF, False),
    "Emoticons": (0x1F600, 0x1F64F, False),
    "Ornamental Dingbats": (0x1F650, 0x1F67F, False),
    "Transport and Map Symbols": (0x1F680, 0x1F6FF, False),
    "Alchemical Symbols": (0x1F700, 0x1F77F, False),
    "Geometric Shapes Extended": (0x1F780, 0x1F7FF, False),
    "Supplemental Arrows-C": (0x1F800, 0x1F8FF, False),
    "Supplemental Symbols and Pictographs": (0x1F900, 0x1F9FF, False),
    "Chess Symbols": (0x1FA00, 0x1FA6F, False),
    "Symbols and Pictographs Extended-A": (0x1FA70, 0x1FAFF, False),
    "Symbols for Legacy Computing": (0x1FB00, 0x1FBFF, False),
    "CJK Unified Ideographs Extension B": (0x20000, 0x2A6DF, False),
    "CJK Unified Ideographs Extension C": (0x2A700, 0x2B73F, False),
    "CJK Unified Ideographs Extension D": (0x2B740, 0x2B81F, False),
    "CJK Unified Ideographs Extension E": (0x2B820, 0x2CEAF, False),
    "CJK Unified Ideographs Extension F": (0x2CEB0, 0x2EBEF, False),
    "CJK Unified Ideographs Extension I": (0x2EBF0, 0x2EE5F, False),
    "CJK Compatibility Ideographs Supplement": (0x2F800, 0x2FA1F, False),
    "CJK Unified Ideographs Extension G": (0x30000, 0x3134F, False),
    "CJK Unified Ideographs Extension H": (0x31350, 0x323AF, False),
    "Tags": (0xE0000, 0xE007F, False),
    "Variation Selectors Supplement": (0xE0100, 0xE01EF, False),
    "Supplementary Private Use Area-A": (0xF0000, 0xFFFFF, False),
    "Supplementary Private Use Area-B": (0x100000, 0x10FFFF, False),
}


_common_characters: list[str] = [
    "À",
    "Á",
    "Â",
    "Ã",
    "Ä",
    "Å",
    "Æ",
    "Ç",
    "È",
    "É",
    "Ê",
    "Ë",
    "Ì",
    "Í",
    "Î",
    "Ï",
    "Ò",
    "Ó",
    "Ô",
    "Õ",
    "Ö",
    "Ø",
    "Œ",
    "Ñ",
    "Ù",
    "Ú",
    "Û",
    "Ü",
    "Ð",
    "þ",
    "Ÿ",
    "Ý",
    "à",
    "á",
    "â",
    "ã",
    "ä",
    "å",
    "æ",
    "ç",
    "è",
    "é",
    "ê",
    "ë",
    "ì",
    "í",
    "î",
    "ï",
    "ò",
    "ó",
    "ô",
    "õ",
    "ö",
    "ø",
    "œ",
    "ñ",
    "ù",
    "ú",
    "û",
    "ü",
    "ð",
    "Þ",
    "ÿ",
    "ý",
    "¡",
    "¿",
    "«",
    "»",
    "‘",
    "’",
    "“",
    "”",
    "‚",
    "‛",
    "„",
    "‟",
    "ß",
    "⁂",
    "☞",
    "☜",
    "±",
    "·",
    "×",
    "÷",
    "°",
    "′",
    "″",
    "‴",
    "‰",
    "¹",
    "²",
    "³",
    "£",
    "¢",
    "©",
    "\xa0",
    "½",
    "⅓",
    "⅔",
    "¼",
    "¾",
    "⅕",
    "⅖",
    "⅗",
    "⅘",
    "⅙",
    "⅚",
    "⅐",
    "⅛",
    "⅜",
    "⅝",
    "⅞",
    "—",
    "–",
    "†",
    "‡",
    "§",
    "‖",
    "¶",
    "¦",
    "º",
    "ª",
]

_unicode_names: dict[str, list[str]] = {}
