"""Guiguts - application to support creation of books for PG"""


import datetime
import os.path
import re
import subprocess
from tkinter import filedialog, messagebox
import webbrowser

from mainwindow import (
    root,
    MainWindow,
    Menu,
    mainimage,
    maintext,
    menubar,
    statusbar,
)

from preferences import preferences
from preferences_dialog import PreferencesDialog
from utilities import isMac


class Guiguts:
    """Top level Guiguts class"""

    def __init__(self):
        """Initialize Guiguts class"""

        self.setPrefsDefaults()

        MainWindow()

        self.initMenus(menubar())

        self.initStatusBar(statusbar())

        self.filename = ""
        self.updateFilenameLabels()

        maintext().focus_set()
        maintext().addModifiedCallback(self.updateTitle)

    def run(self):
        root().mainloop()

    #
    # Update title field with filename
    def updateTitle(self):
        modtitle = " - edited" if maintext().isModified() else ""
        filetitle = " - " + self.filename if self.filename else ""
        root().title("Guiguts 2.0" + modtitle + filetitle)

    #
    # Open and load a text file
    def openFile(self, *args):
        fn = filedialog.askopenfilename(
            filetypes=(("Text files", "*.txt *.html *.htm"), ("All files", "*.*"))
        )
        if fn:
            self.filename = fn
            maintext().doOpen(self.filename)
            self.updateFilenameLabels()

    #
    # Save the current file
    def saveFile(self, *args):
        if self.filename:
            maintext().doSave(self.filename)
        else:
            self.saveasFile()

    #
    # Save current text as new file
    def saveasFile(self, *args):
        fn = filedialog.asksaveasfilename(
            initialfile=os.path.basename(self.filename),
            initialdir=os.path.dirname(self.filename),
            filetypes=[("All files", "*")],
        )
        if fn:
            self.filename = fn
            maintext().doSave(self.filename)
            self.updateFilenameLabels()

    def quitProgram(self, *args):
        root().quit()

    def helpAbout(self, *args):
        messagebox.showinfo(
            title="About Guiguts", message="Here's some information about Guiguts"
        )

    def showMyPreferencesDialog(self, *args):
        PreferencesDialog(root())

    # Handle drag/drop on Macs
    def openDocument(self, args):
        filename = args[0]  # Take first of list of filenames
        maintext().doOpen(filename)
        self.updateFilenameLabels()

    def helpManual(self, *args):
        webbrowser.open("https://www.pgdp.net/wiki/PPTools/Guiguts/Guiguts_Manual")

    def loadImage(self, *args):
        filename = maintext().getImageFilename()
        mainimage().loadImage(filename)
        if preferences.get("ImageWindow") == "Docked":
            mainimage().dockImage()
        else:
            mainimage().floatImage()

    # Handle spawning a process
    def spawnProcess(self, *args):
        try:
            result = subprocess.run(
                ["python", "child.py"],
                input="Convert me to uppercase",
                text=True,
                capture_output=True,
            )
        except FileNotFoundError:
            result = subprocess.run(
                ["python3", "child.py"],
                input="Convert me to uppercase",
                text=True,
                capture_output=True,
            )
        messagebox.showinfo(title="Spawn stdout", message=result.stdout)
        messagebox.showinfo(title="Spawn stderr", message=result.stderr)

    def updateFilenameLabels(self):
        self.updateTitle()
        statusbar().set("filename", os.path.basename(self.filename))

    #
    # Set default preferences - will be overridden by any values set in the Preferences file
    def setPrefsDefaults(self):
        preferences.setDefault("ImageWindow", "Docked")

    def initMenus(self, menubar):
        self.initFileMenu(menubar)
        self.initEditMenu(menubar)
        self.initViewMenu(menubar)
        self.initHelpMenu(menubar)
        self.initOSMenu(menubar)

        if isMac():
            root().createcommand(
                "tk::mac::ShowPreferences", self.showMyPreferencesDialog
            )
            root().createcommand("tk::mac::OpenDocument", self.openDocument)
            root().createcommand("tk::mac::Quit", self.quitProgram)

    def initFileMenu(self, parent):
        menu_file = Menu(parent, "~File")
        menu_file.addButton("~Open...", self.openFile, "Cmd/Ctrl+O")
        menu_file.addButton("~Save", self.saveFile, "Cmd/Ctrl+S")
        menu_file.addButton("Save ~As...", self.saveasFile, "Cmd/Ctrl+Shift+S")
        menu_file.add_separator()
        menu_file.addButton("Spawn ~Process", self.spawnProcess)
        menu_file.add_separator()
        menu_file.addButton("~Quit", self.quitProgram, "Cmd+Q" if isMac() else "")

    def initEditMenu(self, parent):
        menu_edit = Menu(parent, "~Edit")
        menu_edit.addButton("~Undo", "<<Undo>>", "Cmd/Ctrl+Z")
        menu_edit.addButton("~Redo", "<<Redo>>", "Cmd+Shift+Z" if isMac() else "Ctrl+Y")
        menu_edit.add_separator()
        menu_edit.addCutCopyPaste()
        menu_edit.add_separator()
        menu_edit.addButton("Select ~All", "<<SelectAll>>", "Cmd/Ctrl+A")
        menu_edit.add_separator()
        menu_edit.addButton("Pre~ferences...", self.showMyPreferencesDialog)

    def initViewMenu(self, parent):
        menu_view = Menu(parent, "~View")
        menu_view.addButton("~Dock", mainimage().dockImage, "Cmd/Ctrl+D")
        menu_view.addButton("~Float", mainimage().floatImage, "Cmd/Ctrl+F")
        menu_view.addButton("~Load Image", self.loadImage, "Cmd/Ctrl+L")

    def initHelpMenu(self, parent):
        menu_help = Menu(parent, "~Help")
        menu_help.addButton("Guiguts ~Manual", self.helpManual)
        menu_help.addButton("About ~Guiguts", self.helpAbout)

    def initOSMenu(self, parent):
        if isMac():
            # Apple menu
            menu_app = Menu(parent, "", name="apple")
            menu_app.addButton("About ~Guiguts", self.helpAbout)
            menu_app.add_separator()
            # Window menu
            Menu(parent, "Window", name="window")
        else:
            menu_app = None

    def initStatusBar(self, statusbar):
        statusbar.add(
            "rowcol",
            lambda: re.sub(r"(\d)\.(\d)", r"L:\1 C:\2", maintext().get_insert_index()),
            width=10,
        )
        statusbar.add("filename", width=12)
        statusbar.add(
            "time", lambda: datetime.datetime.now().strftime("%H:%M:%S"), width=8
        )


if __name__ == "__main__":
    Guiguts().run()