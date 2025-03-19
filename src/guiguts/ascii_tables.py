"""ASCII table special effects functionality."""

import logging
from enum import StrEnum, auto
import tkinter as tk
from tkinter import ttk
import regex as re

from guiguts.maintext import maintext, HighlightTag
from guiguts.preferences import (
    PrefKey,
    preferences,
    PersistentBoolean,
    PersistentInt,
    PersistentString,
)
from guiguts.widgets import ToplevelDialog
from guiguts.utilities import sound_bell, TextWrapper, IndexRowCol

logger = logging.getLogger(__package__)


class JustifyStyle(StrEnum):
    """Enum class to store justification style types."""

    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()


class ASCIITableDialog(ToplevelDialog):
    """Dialog for ASCII special tables effects."""

    manual_page = "Text_Menu#ASCII_Table_Effects"

    def __init__(self) -> None:
        """Initialize ASCII Table dialog."""
        super().__init__("ASCII Table Special Effects", resize_x=False, resize_y=False)

        self.start_mark_name = ASCIITableDialog.get_mark_prefix() + "Start"
        self.end_mark_name = ASCIITableDialog.get_mark_prefix() + "End"

        self.selected_column = -1

        btn_frame = ttk.Frame(
            self.top_frame, borderwidth=1, relief=tk.GROOVE, padding=5
        )
        btn_frame.grid(row=0, column=0, columnspan=4, sticky="NSEW")

        for row in range(0, 4):
            btn_frame.rowconfigure(row, pad=2)
        for col in range(0, 4):
            btn_frame.columnconfigure(col, pad=2)

        # First row of buttons.
        ttk.Button(
            btn_frame,
            text="Table Select",
            command=self.table_select,
        ).grid(row=0, column=0, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Table Deselect",
            command=self.table_deselect,
        ).grid(row=0, column=1, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Insert Vertical Line",
            command=lambda: self.insert_vert_line("i"),
        ).grid(row=0, column=2, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Add Vertical Line",
            command=lambda: self.insert_vert_line("a"),
        ).grid(row=0, column=3, sticky="NSEW")

        # Second row of buttons.
        ttk.Button(
            btn_frame,
            text="Space Out Table",
            command=self.space_out_table,
        ).grid(row=1, column=0, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Compress Table",
            command=self.compress_table,
        ).grid(row=1, column=1, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Delete Sel. Line",
            command=self.delete_selected_line,
        ).grid(row=1, column=2, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Remove Sel. Line",
            command=self.remove_selected_line,
        ).grid(row=1, column=3, sticky="NSEW")

        # Third row of buttons.
        ttk.Button(
            btn_frame,
            text="Select Prev. Line",
            command=self.select_prev_line,
        ).grid(row=2, column=0, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Select Next Line",
            command=self.select_next_line,
        ).grid(row=2, column=1, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Line Deselect",
            command=self.line_deselect,
        ).grid(row=2, column=2, sticky="NSEW")
        ttk.Button(
            btn_frame,
            text="Auto Columns",
            command=self.auto_columns,
        ).grid(row=2, column=3, sticky="NSEW")

        # Fourth and fifth rows are each Frames within a LabelFrame.
        self.adjust_col_frame = ttk.LabelFrame(
            self.top_frame, text="Adjust Column", padding=10
        )
        self.adjust_col_frame.grid(row=3, column=0, sticky="NSEW")
        self.adjust_col_frame.columnconfigure(0, weight=1)

        adjust_col_row1_frame = ttk.Frame(self.adjust_col_frame)
        adjust_col_row1_frame.grid(row=0, column=0, pady=2, sticky="NSEW")
        adjust_col_row2_frame = ttk.Frame(self.adjust_col_frame)
        adjust_col_row2_frame.grid(row=1, column=0, pady=2, sticky="NSEW")

        # Populate the first row.
        label_justify = ttk.Label(adjust_col_row1_frame, text="Justify")
        label_justify.grid(row=0, column=1, padx=(0, 5), pady=2, sticky="NSEW")

        justify_style = PersistentString(PrefKey.ASCII_TABLE_JUSTIFY)
        justify_left = ttk.Radiobutton(
            adjust_col_row1_frame,
            text="Left",
            variable=justify_style,
            value=JustifyStyle.LEFT,
            takefocus=False,
        )
        justify_left.grid(row=0, column=2, pady=2, sticky="NSEW")

        justify_center = ttk.Radiobutton(
            adjust_col_row1_frame,
            text="Center",
            variable=justify_style,
            value=JustifyStyle.CENTER,
            takefocus=False,
        )
        justify_center.grid(row=0, column=3, pady=2, sticky="NSEW")

        justify_right = ttk.Radiobutton(
            adjust_col_row1_frame,
            text="Right",
            variable=justify_style,
            value=JustifyStyle.RIGHT,
            takefocus=False,
        )
        justify_right.grid(row=0, column=4, padx=(0, 15), pady=2, sticky="NSEW")

        label_indent = ttk.Label(adjust_col_row1_frame, text="Indent")
        label_indent.grid(row=0, column=5, padx=5, pady=2, sticky="NSEW")
        indent_value_entry = tk.Entry(
            adjust_col_row1_frame,
            width=5,
            textvariable=PersistentInt(PrefKey.ASCII_TABLE_INDENT),
        )
        indent_value_entry.grid(row=0, column=6, padx=0, pady=2, sticky="NSEW")

        hanging_checkbox = ttk.Checkbutton(
            adjust_col_row1_frame,
            text="Hanging",
            variable=PersistentBoolean(PrefKey.ASCII_TABLE_HANGING),
        )
        hanging_checkbox.grid(row=0, column=7, padx=10, pady=2, sticky="NSEW")

        # Populate the second row.
        rewrap_cols_checkbox = ttk.Checkbutton(
            adjust_col_row2_frame,
            text="Rewrap Cols",
            variable=PersistentBoolean(PrefKey.ASCII_TABLE_REWRAP),
        )
        rewrap_cols_checkbox.grid(row=0, column=2, padx=10, pady=2, sticky="NSEW")

        move_left_button = ttk.Button(
            adjust_col_row2_frame,
            text="Move Left",
            command=lambda: self.column_adjust(-1),
            width=12,
        )
        move_left_button.grid(row=0, column=1, sticky="NSEW")

        move_right_button = ttk.Button(
            adjust_col_row2_frame,
            text="Move Right",
            command=lambda: self.column_adjust(1),
            width=12,
        )
        move_right_button.grid(row=0, column=3, sticky="NSEW")

        self.selected_col_width_label = ttk.Label(adjust_col_row2_frame)
        self.selected_col_width_label.grid(row=0, column=4, sticky="NSEW")
        self.column_width_refresh(-1)

        self.table_select()

    def column_adjust(self, direction: int) -> int:
        """Move a column dividing line left or right.

        If 'Rewrap Cols' ticked, text in the selected column is rewrapped to fit the change
        in width. It is always justified left at this point. Each line of text in the column
        will have padding added later so that it can be centered or right-justified as required
        by the 'Justify' radio button choice.

        Args:
            direction: -1 to move left one column, 1 to move right one column
        """
        # Is there a selected column divider?
        if self.selected_column < 0:
            return 0
        # Use a single copy of the class.
        wrapper = TextWrapper()
        # Is 'Rewrap Cols' ticked?
        if preferences.get(PrefKey.ASCII_TABLE_REWRAP):
            direction -= 1  # -2 or 0
            tbl = []
            col = []
            selection = maintext().get(self.start_mark_name, self.end_mark_name)
            selection = selection.rstrip()
            temp_line = maintext().get(
                f"{self.start_mark_name} linestart", f"{self.start_mark_name} lineend"
            )
            col.append(0)
            while len(temp_line):
                indx = temp_line.find("|")
                if indx > -1:
                    # Found the "|" character on the line.
                    col.append((indx + 1 + col[-1]))
                    # Chomp the column up to and including its column divider. If there
                    # is a column divider at column 0, it delineates a zero-width column.
                    temp_line = temp_line[indx + 1 :]
                    continue
                temp_line = ""
            column_index = 0
            for indx, value in enumerate(col):
                if self.selected_column == value - 1:
                    column_index = indx
                    break
            # Belt-n-braces.
            if column_index == 0:
                self.selected_column = -1
                self.remove_column_highlighting()
                self.refresh_table_highlighting()
                return 0
            # Remove trailing spaces from each row of table copy.
            selection = re.sub(r"\n +$", "\n", selection)
            table = selection.split("\n")
            blank_line = ""
            # In each iteration of a 'for' loop, Perl creates an alias instead of a value. This means that
            # if you make any changes to the iterator, the changes also reflect in the elements of the array.
            # The substr() call in the Perl version, lines 520-524, that the assignment below to 'cell' is
            # meant to emulate, changes the iterator hence changes the elements of the 'table' array.
            #   cell: becomes the substring extracted from the iterator ('line' here) by substr()
            #   line: becomes what is left in the iterator/table element after the extraction by substr().
            # Emulate the latter in Python.
            new_table = []
            for line in table:
                start = col[column_index - 1]
                length = col[column_index] - col[column_index - 1] - 1
                cell = line[start : start + length]
                # Record what is left of the iterator after the substring is removed.
                new_element = line[0:start] + line[start + length :]
                if blank_line == "":
                    # If the changed iterator contains at least one "|" and no other characters
                    # except space characters then set 'blank_line' to the iterator's contents.
                    if re.search(r"^[ |]+$", new_element) and re.search(
                        r"\|", new_element
                    ):
                        blank_line = new_element
                cell += " "
                # If cell contains only spaces change it to the empty string.
                cell = re.sub(r"^\s+$", "", cell)
                tbl.append(cell)
                new_table.append(new_element)
            # Replace 'table' so its elements reflect the changes that substr() made to them in the Perl version.
            table = new_table.copy()
            # If no blank lines found in table, make one up from the first table row
            # that contains "|" by replacing all characters other than "|" with a space
            # character.
            if blank_line == "":
                for line in table:
                    if re.search(r"\|", line):
                        blank_line = re.sub(r"[^\|]", " ", line)
                        break
            cells: list[int] = []
            cell_height = 1
            cell_flag = False
            for cell in tbl:
                if cell and not cell_flag and not cells:
                    cells.append(0)
                    cell_flag = True
                    continue
                if cell and not cell_flag:
                    cells.append(cell_height)
                    cell_height = 1
                    cell_flag = True
                    continue
                # Could change below to 'not(len(cell) or cell_flag)' using DeMorgan's Law.
                if not cell and not cell_flag:
                    cell_height += 1
                    continue
                if not cell and cell_flag:
                    cell_flag = False
                    cell_height += 1
                    continue
                if cell and cell_flag:
                    cell_height += 1
                    continue
            cells.append(cell_height)
            if not cells[0]:
                cells.pop(0)
            tblwr = []
            # Get left-margin and first-margin values for rewrapping.
            lm, fm = 0, 0
            if preferences.get(PrefKey.ASCII_TABLE_HANGING):
                lm = preferences.get(PrefKey.ASCII_TABLE_INDENT)
            else:
                fm = preferences.get(PrefKey.ASCII_TABLE_INDENT)
            # Text will be rewrapped within this width.
            width = col[column_index] - col[column_index - 1] + direction
            for cell_cnt in cells:
                temp_line = ""
                for _cnt in range(1, cell_cnt + 1):
                    if len(tbl) == 0:
                        break
                    temp_line += tbl.pop(0)
                # Wrap the cell text.
                wrapper.width = width
                wrapper.initial_indent = fm * " "
                wrapper.subsequent_indent = lm * " "
                wrapped = wrapper.fill(temp_line)
                tblwr.append(wrapped)
            # In the following, the wrapped text will have appropriate padding
            # added if the text is required to be centered or right-justified
            # within the width in which it has just been wrapped.
            cell_height = 0
            # Belt-n-braces.
            if width < 0:
                return 0
            temp_table = []
            justify_style = preferences.get(PrefKey.ASCII_TABLE_JUSTIFY)
            for wrpd in tblwr:
                temp_array = wrpd.split("\n")
                diff = cells[cell_height] - len(temp_array)
                if diff < 1:
                    for _cnt in range(1, cells[cell_height] + 1):
                        wline = temp_array.pop(0)
                        # Belt-n-braces.
                        if len(wline) > width:
                            return 0
                        # Padding to fill width for left-justified text.
                        pad = width - len(wline)
                        # Left-padding if required to center column text.
                        padl = int(pad / 2)
                        # Right-padding if required to center column text.
                        padr = int(pad / (2 + 0.5))
                        if justify_style == JustifyStyle.LEFT:
                            wline = wline + " " * pad
                        elif justify_style == JustifyStyle.CENTER:
                            wline = " " * padl + wline + " " * padr
                        else:
                            wline = " " * pad + wline
                        temp_line = table.pop(0)
                        # Python equivalent of 'substr($temp_line, $col[$column_index - 1], 0, $wline)'
                        temp_line = (
                            temp_line[0 : col[column_index - 1]]
                            + wline
                            + temp_line[col[column_index - 1] :]
                        )
                        temp_table.append(temp_line + "\n")
                    for array_element in temp_array:
                        # Padding to fill width for left-justified text.
                        pad = width - len(array_element)
                        # Belt-n-braces.
                        if pad < 0:
                            return 0
                        # Left-padding if required to center column text.
                        padl = int(pad / 2)
                        # Right-padding if required to center column text.
                        padr = int(pad / (2 + 0.5))
                        if justify_style == JustifyStyle.LEFT:
                            array_element = array_element + " " * pad
                        elif justify_style == JustifyStyle.CENTER:
                            array_element = " " * padl + array_element + " " * padr
                        else:
                            array_element = " " * pad + array_element
                        # Is there a blank line after row to which to wrap down into?
                        if not blank_line:
                            # No.
                            return 0
                        temp_line = blank_line
                        # Python equivalent of 'substr($temp_line, $col[$column_index - 1], 0, $wline)'
                        temp_line = (
                            temp_line[0 : col[column_index - 1]]
                            + array_element
                            + temp_line[col[column_index - 1] :]
                        )
                        temp_table.append(temp_line + "\n")
                        # Is there a blank line after row to which to wrap down into?
                        if not blank_line:
                            # No.
                            return 0
                        temp_line = blank_line
                        # Python equivalent of 'substr($temp_line, $col[$column_index - 1], 0, " " x $width)'
                        temp_line = (
                            temp_line[0 : col[column_index - 1]]
                            + " " * width
                            + temp_line[col[column_index - 1] :]
                        )
                        temp_table.append(temp_line + "\n")
                if diff > 0:
                    for array_element in temp_array:
                        # Padding to fill width for left-justified text.
                        pad = width - len(array_element)
                        # Belt-n-braces.
                        if pad < 0:
                            return 0
                        # Left-padding if required to center column text.
                        padl = int(pad / 2)
                        # Right-padding if required to center column text.
                        padr = int(pad / (2 + 0.5))
                        if justify_style == JustifyStyle.LEFT:
                            array_element = array_element + " " * pad
                        elif justify_style == JustifyStyle.CENTER:
                            array_element = " " * padl + array_element + " " * padr
                        else:
                            array_element = " " * pad + array_element
                        if len(array_element) > width:
                            return 0
                        temp_line = table.pop(0)
                        temp_line = (
                            temp_line[0 : col[column_index - 1]]
                            + array_element
                            + temp_line[col[column_index - 1] :]
                        )
                        temp_table.append(temp_line + "\n")
                    for _val in range(1, diff + 1):
                        if not table:
                            break
                        temp_line = table.pop(0)
                        # Python equivalent of 'substr($temp_line, $col[$column_index - 1], 0, " " x $width)'
                        temp_line = (
                            temp_line[0 : col[column_index - 1]]
                            + " " * width
                            + temp_line[col[column_index - 1] :]
                        )
                        temp_table.append(temp_line + "\n")
                cell_height += 1
            table = []
            cell_flag = False
            for array_entry in temp_table:
                if re.search(r"^[ |]+$", array_entry) and not cell_flag:
                    cell_flag = True
                    table.append(array_entry)
                else:
                    if re.search(r"^[ |]+$", array_entry):
                        continue
                    table.append(array_entry)
                    cell_flag = False

        # Temporary value
        return 0

    def column_width_refresh(self, row: int) -> None:
        """Calculate the width of selected column and display it.

        Args:
            row: Row to use to calculate column width on. Negative to clear width.
        """
        width_text = ""
        if row >= 0 and self.selected_column >= 0:
            column_width_text = maintext().get(f"{row}.0", f"{row}.end")
            cells = column_width_text.split("|")
            if self.selected_column < len(cells):
                width_text = f" {self.selected_column} (width {len(cells[-self.selected_column])})"
        self.adjust_col_frame["text"] = f"Adjust Column{width_text}"

    def table_select(self) -> None:
        """Handle click on 'Table Select' button."""
        maintext().undo_block_begin()
        # Clear any marks and tags from previous ASCII table activity.
        self.do_table_deselect()
        # Set the marks and tags for a new table.
        self.do_table_select()

    def do_table_select(self) -> None:
        """Mark and tag the selected text as a table to be worked on.
        If column selection, table is whole of each line in the column selection."""
        ranges = maintext().selected_ranges()
        if len(ranges) == 0:
            return

        # Always start at beginning of first line of the selection.
        tblstart = maintext().rowcol(f"{ranges[0].start.index()} linestart")
        # Always end at start of line following the selection end (unless already there).
        if ranges[-1].end.col == 0:
            tblend = maintext().rowcol(f"{ranges[-1].end.index()}")
        else:
            tblend = maintext().rowcol(f"{ranges[-1].end.index()} +1l linestart")
        # Mark the beginning and end of the selected table.
        maintext().set_mark_position(
            self.start_mark_name,
            tblstart,
            gravity=tk.LEFT,
        )
        maintext().set_mark_position(
            self.end_mark_name,
            tblend,
            gravity=tk.RIGHT,
        )
        # The 'sel' tag has priority so its highlighting remains even if we add the
        # table body tag highlighting. To have our table body tag highlight the whole
        # of the selection (i.e. our table), clear selection first.
        maintext().clear_selection()
        self.refresh_table_highlighting()
        self.selected_column = -1
        self.column_width_refresh(-1)

    def table_deselect(self) -> None:
        """Handle click on 'Table Deselect' button."""
        maintext().undo_block_begin()
        self.do_table_deselect()

    def do_table_deselect(self) -> None:
        """Remove tags and marks added by do_table_select()."""
        mark = "1.0"
        # Delete all marks we set.
        while mark_next := maintext().mark_next(mark):
            if mark_next.startswith((self.start_mark_name, self.end_mark_name)):
                mark = maintext().index(mark_next)
                maintext().mark_unset(mark_next)
            else:
                mark = mark_next
        self.selected_column = -1
        self.column_width_refresh(-1)
        self.remove_column_highlighting()
        self.refresh_table_highlighting()

    def insert_vert_line(self, mode: str) -> None:
        """Handle click on 'Insert Vertical Line & 'Add Vertical Line' buttons.

        Arg:
            mode: 'i' when called by Insert Vertical Line button
                  'a' when called by Add Vertical Line button
        """
        maintext().undo_block_begin()
        self.do_insert_vert_line(mode)

    def do_insert_vert_line(self, mode: str) -> None:
        """Add a column dividing line according to mode (see above)."""
        # Has user selected a table?
        if not self.table_is_marked():
            # Warn them and exit as there is nothing to process.
            sound_bell()
            return
        made_a_dividing_line = False
        # Get column position of insert cursor.
        cursor_column = maintext().get_insert_index().col
        # Set start and end row/col of table from marks for "|" insert loop.
        start_row = maintext().rowcol(self.start_mark_name).row
        end_row = maintext().rowcol(self.end_mark_name).row
        end_col = maintext().rowcol(self.end_mark_name).col
        # Back up a row if last row of table is blank.
        if end_col == 0:
            end_row -= 1
        # 'insert' (mode == 'i') a vertical line or 'add' (mode == 'a') a vertical line.
        if mode == "i":
            # 'Insert Vertical Line' button. This is the easy one. Unconditionally
            # insert a "|" character to the right of the cursor position for each
            # file line in the table. Pushes rest of each line to the right.
            for table_row in range(start_row, end_row + 1):
                row_end_column = maintext().rowcol(f"{table_row}.0 lineend").col
                row_end_index = maintext().rowcol(f"{table_row}.0 lineend").index()
                # If necessary, fill row with spaces to the cursor column position.
                if row_end_column < cursor_column:
                    maintext().insert(
                        row_end_index, (" " * (cursor_column - row_end_column))
                    )
                # Insert a "|" character on this line at cursor position.
                maintext().insert(f"{table_row}.{cursor_column}", "|")
            made_a_dividing_line = True
        else:
            # Assume mode == 'a'.
            # 'Add Vertical Line' button. A little more tricky as we should first
            # check there is a column of space characters immediately to the right
            # of the cursor position. That column is then replaced by a column of
            # '|' characters. If there is no column of space characters we
            # may still have altered the table by padding lines with space characters
            # so repaint table background colour, etc., as if we had added stiles.
            found_column_of_spaces = True
            for table_row in range(start_row, end_row + 1):
                row_end_column = maintext().rowcol(f"{table_row}.0 lineend").col
                row_end_index = maintext().rowcol(f"{table_row}.0 lineend").index()
                # If necessary, fill row with spaces to the cursor column position.
                if row_end_column < cursor_column:
                    maintext().insert(
                        row_end_index, (" " * (cursor_column - row_end_column))
                    )
                next_char = maintext().get(
                    f"{table_row}.{cursor_column}", f"{table_row}.{cursor_column} +1c"
                )
                if next_char != " ":
                    found_column_of_spaces = False
            # We've run down the table to see if we have a column of spaces to the
            # right of the cursor position. If we have then replace that column with
            # "|" characters.
            if found_column_of_spaces:
                for table_row in range(start_row, end_row + 1):
                    # Replace a space character with a "|" character at cursor position
                    # on this file line.
                    maintext().replace(
                        f"{table_row}.{cursor_column}",
                        f"{table_row}.{cursor_column} +1c",
                        "|",
                    )
                    made_a_dividing_line = True
        # All inserts/replacements done and/or table lines padded with spaces.
        self.refresh_table_highlighting()
        # If we have inserted/added a divider then highlight it and display new column's width.
        if made_a_dividing_line:
            self.selected_column = self.get_selected_column_from_rowcol(
                IndexRowCol(table_row, cursor_column)
            )
            self.column_width_refresh(start_row)
            self.highlight_column_divider()

    def space_out_table(self) -> None:
        """Handle click on 'Space Out Table' button."""
        maintext().undo_block_begin()
        self.do_space_out_table()

    def do_space_out_table(self) -> None:
        """Add empty lines between table rows."""
        ranges = maintext().tag_ranges(HighlightTag.TABLE_BODY)
        # Has user selected a table?
        if len(ranges) == 0:
            # No, so warn them and exit as there is nothing to process.
            sound_bell()
            return
        # Get start and end row/col of table from marks.
        start_row = maintext().rowcol(self.start_mark_name).row
        start_col = maintext().rowcol(self.start_mark_name).col
        end_row = maintext().rowcol(self.end_mark_name).row
        end_col = maintext().rowcol(self.end_mark_name).col
        self.remove_column_highlighting()
        self.refresh_table_highlighting()
        # Back up a row if last row of table is blank.
        if end_col == 0:
            end_row -= 1
        # Get copy of first row of table. If table has any column dividers they
        # will be present in the copy.
        blank_row_text = maintext().get(
            f"{start_row}.{start_col} linestart", f"{start_row}.end"
        )
        # Replace in this copy all characters, other than '|', with a space.
        blank_row_text = re.sub(r"[^|]", " ", blank_row_text)
        # Back up to the penultimate row of the table.
        end_row -= 1
        # Insert 'blank_row_text' lines between each row of the table. If a
        # blank row already exists in the table don't add a new one. Instead
        # replace it with 'blank_row_text'. Work from bottom of table toward
        # the top.
        prev_row_is_blank = False
        while end_row >= start_row:
            if (
                maintext().get(f"{end_row}.0", f"{end_row}.end") != ""
                and not prev_row_is_blank
            ):
                prefixed_blank_row_text = "\n" + blank_row_text
                maintext().insert(f"{end_row}.end", f"{prefixed_blank_row_text}")
            elif (
                maintext().get(f"{end_row}.0", f"{end_row}.end") != ""
                and prev_row_is_blank
            ):
                prev_row_is_blank = False
            elif maintext().get(f"{end_row}.0", f"{end_row}.end") == "":
                # Have encountered a blank line in the table. Replace this
                # with 'blank_row_text' in order to display continuation
                # of any column dividers in the table. This situation will
                # occur when the user has added a blank line to the table
                # and has omitted to continue a column divider that is on
                # the rows above and below the blank line.
                maintext().delete(f"{end_row}.0", f"{end_row}.end")
                maintext().insert(f"{end_row}.end", f"{blank_row_text}")
                prev_row_is_blank = True
            end_row -= 1

    def compress_table(self) -> None:
        """Handle click on 'Compress Table' button."""
        maintext().undo_block_begin()
        self.do_compress_table()

    def do_compress_table(self) -> None:
        """Remove the 'blank' spacing lines between table rows."""
        ranges = maintext().tag_ranges(HighlightTag.TABLE_BODY)
        # Has user selected a table?
        if len(ranges) == 0:
            # No, so warn them and exit as there is nothing to process.
            sound_bell()
            return
        # Get start and end row/col of table from marks.
        start_row = maintext().rowcol(self.start_mark_name).row
        end_row = maintext().rowcol(self.end_mark_name).row
        end_col = maintext().rowcol(self.end_mark_name).col
        self.remove_column_highlighting()
        self.refresh_table_highlighting()
        # Back up a row if last row of table is blank.
        if end_col == 0:
            end_row -= 1
        while end_row >= start_row:
            row_text = maintext().get(f"{end_row}.0", f"{end_row}.end")
            if re.match(r"^[ |]*$", row_text):
                maintext().delete(f"{end_row}.0 -1c", f"{end_row}.end")
            end_row -= 1

    def delete_selected_line(self) -> None:
        """Handle click on 'Delete Sel. Line' button."""
        maintext().undo_block_begin()
        self.do_delete_selected_line()

    def do_delete_selected_line(self) -> None:
        """Delete selected column divider from each table row in which it appears."""
        # NB 'ranges' is a tuple that contains zero or more pairs of indexes as strings.
        #    e.g. ("1.2", "1.3", "2.2", "2.3", "3.2", "3.3", ...)
        # If a there is a selected column divider then there will be as many pairs of
        # indexes in the tuple as there are rows in the table. If no column divider is
        # selected then the tuple is empty.
        ranges_tuple = maintext().tag_ranges(HighlightTag.TABLE_COLUMN)
        # Is there a selected column divider in the table?
        if len(ranges_tuple) == 0:
            return
        # Convert tuple to a list as it's easier to manipulate.
        ranges = list(ranges_tuple)
        self.remove_column_highlighting()
        self.refresh_table_highlighting()
        # Now delete the selected column divider from each table row in which it appears.
        while ranges:
            index2 = ranges.pop()
            index1 = ranges.pop()
            if maintext().get(index1, index2) == "|":
                maintext().delete(index1, index2)
        self.selected_column = -1
        self.column_width_refresh(-1)

    def remove_selected_line(self) -> None:
        """Handle click on 'Delete Sel. Line' button."""
        maintext().undo_block_begin()
        self.do_remove_selected_line()

    def do_remove_selected_line(self) -> None:
        """Delete selected column divider from each table row in which it appears."""
        # NB 'ranges' is a tuple that contains zero or more pairs of indexes as strings.
        #    e.g. ("1.2", "1.3", "2.2", "2.3", "3.2", "3.3", ...)
        # If a there is a selected column divider then there will be as many pairs of
        # indexes in the tuple as there are rows in the table. If no column divider is
        # selected then the tuple is empty.
        ranges_tuple = maintext().tag_ranges(HighlightTag.TABLE_COLUMN)
        # Is there a selected column divider in the table?
        if len(ranges_tuple) == 0:
            return
        # Convert tuple to a list as it's easier to manipulate.
        ranges = list(ranges_tuple)
        self.remove_column_highlighting()
        # Now delete the selected column divider from each table row in which it appears.
        while ranges:
            index2 = ranges.pop()
            index1 = ranges.pop()
            if maintext().get(index1, index2) == "|":
                maintext().replace(index1, index2, " ")
        self.refresh_table_highlighting()
        self.selected_column = -1
        self.column_width_refresh(-1)

    def select_prev_line(self) -> None:
        """Handle click on 'Select Prev. Line' button."""
        maintext().undo_block_begin()
        self.do_select_prev_line()

    def do_select_prev_line(self) -> None:
        """Select the previous column divider."""

        # Look for the 'previous' column divider, starting search along first
        # row of the table at the currently selected divider. If there isn't a
        # currently selected divider then start the search along first row of the
        # table at the column position of the cursor. If the cursor is outside
        # the table then start search from the end of the first row of the table.
        # The search looks along the first row for a '|' character, the column
        # divider character. It assumes that if it finds one then that character
        # is repeated in the same column on all the other rows down to the last
        # row. This means that if there is a random '|' character in the first
        # row then it thinks that is the top of a column divider line. A random
        # '|' on any other row is ignored in the search.

        # Is there a table selected?
        if not self.table_is_marked():
            # No. Just return.
            return
        # Is there a highlighted column divider line in table?
        ranges = maintext().tag_ranges(HighlightTag.TABLE_COLUMN)
        if len(ranges) == 0:
            # No currently selected column divider. Try current cursor position instead.
            start_index = maintext().get_insert_index().index()
            # If it's outside the table, start search at end of first table row.
            if maintext().compare(
                start_index, "<", self.start_mark_name
            ) or maintext().compare(start_index, ">", self.end_mark_name):
                # Cursor is outside of the table.
                start_index = maintext().index(f"{self.start_mark_name} lineend")
            else:
                # Start search from cursor column position on first table row.
                _, cur_col = start_index.split(".")
                tab_row, _ = maintext().index(self.start_mark_name).split(".")
                # First row of table + cursor column position.
                start_index = tab_row + "." + cur_col
        else:
            # There is a selected column divider line. Start search from before the divider character.
            start_index = str(ranges[0])
            self.remove_column_highlighting()
        # Find previous '|' character on this row.
        stop_index = maintext().index(f"{start_index} linestart")
        # stop_index = maintext().rowcol(f"{start_index} +linestart").index()
        prev_column = maintext().search(
            "|", start_index, backwards=True, stopindex=stop_index
        )
        if prev_column == "":
            # If no previous '|' on this row, wrap by looking again from the end of the row.
            # stop_index = maintext().rowcol(f"{start_index} linestart").index()
            start_index = maintext().index(f"{start_index} lineend")
            stop_index = maintext().index(f"{start_index} linestart")
            prev_column = maintext().search(
                "|", start_index, backwards=True, stopindex=stop_index
            )
            if prev_column == "":
                # Return silently.
                return
        # Here when a previous '|' is found, either from initial backwards search or after
        # wrapping and searching again from the end of the row.
        self.refresh_table_highlighting()
        # Highlight the column divider we've just found.
        rowcol = maintext().rowcol(prev_column)
        self.selected_column = self.get_selected_column_from_rowcol(rowcol)
        self.column_width_refresh(rowcol.row)
        self.highlight_column_divider()

    def select_next_line(self) -> None:
        """Handle click on 'Select Prev. Line' button."""
        maintext().undo_block_begin()
        self.do_select_next_line2()

    def do_select_next_line2(self) -> None:
        """Select the next column divider."""
        if not self.table_is_marked():
            return
        n_cols = len(self.get_table()[0])
        if self.selected_column >= 0:
            self.selected_column = (self.selected_column + 1) % n_cols
        else:
            insert_rowcol = maintext().get_insert_index()
            if maintext().compare(
                insert_rowcol.index(), "<", self.start_mark_name
            ) or maintext().compare(insert_rowcol.index(), ">", self.end_mark_name):
                self.selected_column = 0
            else:
                self.selected_column = self.get_selected_column_from_rowcol(
                    insert_rowcol
                )
        self.column_width_refresh(maintext().rowcol(self.start_mark_name).row)
        self.highlight_column_divider()

    def do_select_next_line(self) -> None:
        """Select the next column divider."""

        # Look for the 'next' column divider, starting search along first row of
        # the table at the currently selected divider. If there isn't a currently
        # selected divider then start the search along first row of the table
        # at the column position of the cursor. If the cursor is outside the
        # table then start search from the start of the first row of the table.
        # The search looks along the first row for a '|' character, the column
        # divider character. It assumes that if it finds one then that character
        # is repeated in the same column on all the other rows down to the last
        # row. This means that if there is a random '|' character in the first
        # row then it thinks that is the top of a column divider line. A random
        # '|' on any other row is ignored in the search.

        # Is there a table selected?
        if not self.table_is_marked():
            return
        # Is there a highlighted column divider line in the table?
        ranges = maintext().tag_ranges(HighlightTag.TABLE_COLUMN)
        if len(ranges) == 0:
            # No currently selected column divider. Try current cursor position instead.
            start_index = maintext().get_insert_index().index()
            # If it's outside the table, start search at start of first table row.
            if maintext().compare(
                start_index, "<", self.start_mark_name
            ) or maintext().compare(start_index, ">", self.end_mark_name):
                # Cursor is outside of the table.
                start_index = maintext().index(f"{self.start_mark_name} linestart")
            else:
                # Start search from cursor column position on first table row.
                _, cur_col = start_index.split(".")
                tab_row, _ = maintext().index(self.start_mark_name).split(".")
                # First row of table + cursor column position.
                start_index = tab_row + "." + cur_col
        else:
            # There is a selected column divider line. Start search from after the divider character.
            start_index = str(ranges[1])
            self.remove_column_highlighting()
        # Find next '|' character on this row.
        stop_index = maintext().index(f"{start_index} lineend")
        next_column = maintext().search(
            "|", start_index, forwards=True, stopindex=stop_index
        )
        if next_column == "":
            # If no next '|' on this row, wrap by looking again from the start of the row.
            start_index = maintext().index(f"{start_index} linestart")
            stop_index = maintext().index(f"{start_index} lineend")
            next_column = maintext().search(
                "|", start_index, forwards=True, stopindex=stop_index
            )
            if next_column == "":
                # Return silently.
                return
        # Here when a next '|' is found, either from initial forwards search or after
        # wrapping and searching again from the start of the row.
        self.refresh_table_highlighting()
        # Highlight the column divider we've just found.
        rowcol = maintext().rowcol(next_column)
        self.selected_column = self.get_selected_column_from_rowcol(rowcol)
        self.column_width_refresh(rowcol.row)
        self.highlight_column_divider()

    def line_deselect(self) -> None:
        """Handle click on 'Line Deselect' button."""
        maintext().undo_block_begin()
        self.do_line_deselect()

    def do_line_deselect(self) -> None:
        """Deselect the currently highlighted column divider."""
        # Is there a table selected?
        if not self.table_is_marked():
            return
        self.remove_column_highlighting()
        self.refresh_table_highlighting()
        self.selected_column = -1
        self.column_width_refresh(-1)

    def auto_columns(self) -> None:
        """Handle click on 'Auto Columns' button."""
        maintext().undo_block_begin()
        self.do_auto_columns()

    def do_auto_columns(self) -> None:
        """Automatically split text into table columns at multi-space points
        using vertical column dividers at those points."""
        ranges = maintext().tag_ranges(HighlightTag.TABLE_BODY)
        if len(ranges) == 0:
            return

        tbl = self.get_table(strip_cells=True)
        col_widths = self.get_max_column_widths(tbl)
        for row in tbl:
            for col_num, col in enumerate(row):
                row[col_num] += " " * (col_widths[col_num] - len(col))
        self.put_table(tbl)
        self.refresh_table_highlighting()
        self.selected_column = -1
        self.column_width_refresh(-1)

    def get_table(self, strip_cells: bool = False) -> list[list[str]]:
        """Get table from file and return as a list of lists.

        Args:
            strip_cells: If True, contents of cells are stripped

        Returns:
            Table with each cell in one element of 2D array, i.e.
            all sublists have the same number of elements(=table columns).
        """
        table: list[list[str]] = []
        ranges = maintext().tag_ranges(HighlightTag.TABLE_BODY)
        if len(ranges) == 0:
            return table
        table_text = maintext().get(self.start_mark_name, self.end_mark_name)
        split_regex = r"\|" if "|" in table_text else r"  +"
        text_rows = table_text.split("\n")
        if text_rows[-1] == "":  # Trailing empty line.
            del text_rows[-1]
        for text_row in text_rows:
            text_row = re.sub(r"^\||\|$", "", text_row.rstrip())
            text_cells = re.split(split_regex, text_row)
            table_row: list[str] = []
            for cell_text in text_cells:
                if strip_cells:
                    cell_text = cell_text.strip()
                table_row.append(cell_text)
            table.append(table_row)
        max_cols = max(len(row) for row in table)
        # "Square off" table, making all rows have max_cols columns
        for row in table:
            row.extend(["" for _ in range(len(row), max_cols)])
        return table

    def put_table(self, table: list[list[str]]) -> None:
        """Put list of lists back into file as an ASCII table."""
        text_rows: list[str] = []
        for row in table:
            text_rows.append(" |".join(row))
        text_table = " |\n".join(text_rows) + " |\n"
        maintext().replace(self.start_mark_name, self.end_mark_name, text_table)

    def get_max_column_widths(self, table: list[list[str]]) -> list[int]:
        """Get the max cell widths for each column in given table.

        Args:
            table: Table cells in 2D array.

        Returns:
            List of max cell widths.
        """
        cols: list[int] = []
        for row in table:
            for col_num, cell in enumerate(row):
                size = len(cell)
                if col_num >= len(cols):
                    cols.append(size)
                elif size > cols[col_num]:
                    cols[col_num] = size
        return cols

    def refresh_table_highlighting(self) -> None:
        """Refresh the table highlighting after an edit. Remove tag from
        whole file and attempt to add it to table. It's OK if the table
        isn't marked at the moment. This refreshing avoids parts of table
        not being highlighted after editing."""
        maintext().tag_remove(HighlightTag.TABLE_BODY, "1.0", tk.END)
        try:
            maintext().tag_add(
                HighlightTag.TABLE_BODY, self.start_mark_name, self.end_mark_name
            )
        except tk.TclError:
            pass  # OK if no start/end tags

    def remove_column_highlighting(self) -> None:
        """Remove column highlighting from whole file (to be safe)."""
        maintext().tag_remove(HighlightTag.TABLE_COLUMN, "1.0", tk.END)

    def get_selected_column_from_rowcol(self, rowcol: IndexRowCol) -> int:
        """Return which column is currently selected, given an rowcol.

        Returns:
            Number of "|" characters on line before given col.
            Returns -1 if line has no "|" characters.
        """
        line = maintext().get(f"{rowcol.row}.0", f"{rowcol.row}.end")
        if "|" not in line:
            return -1
        return line.count("|", 0, rowcol.col)

    def table_is_marked(self) -> bool:
        """Returns 'False' if no table has been selected and marked."""
        table_start_mark_present = False
        table_end_mark_present = False
        for mark in maintext().mark_names():
            if mark.startswith(self.start_mark_name):
                table_start_mark_present = True
            elif mark.startswith(self.end_mark_name):
                table_end_mark_present = True
        return table_start_mark_present and table_end_mark_present

    def highlight_column_divider(self) -> None:
        """Highlight currently selected column divider."""
        self.remove_column_highlighting()
        if self.selected_column < 0:
            return
        start = maintext().rowcol(self.start_mark_name)
        end = maintext().rowcol(self.end_mark_name)
        # Back up a row if last row of table is blank.
        if end.col == 0:
            end.row -= 1
        for table_row in range(start.row, end.row + 1):
            pipe_index = f"{table_row}.0 -1c"
            for _ in range(self.selected_column + 1):
                pipe_index = maintext().search(
                    "|", f"{pipe_index}+1c", f"{table_row}.end"
                )
                if not pipe_index:
                    break
            if pipe_index:
                maintext().tag_add(HighlightTag.TABLE_COLUMN, pipe_index)
