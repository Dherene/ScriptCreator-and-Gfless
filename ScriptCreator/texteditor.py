#-------------------------------------------------------------------------
# qsci_simple_pythoneditor.pyw
#
# QScintilla sample with PyQt
#
# Eli Bendersky (eliben@gmail.com)
# This code is in the public domain
#-------------------------------------------------------------------------
import sys

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciLexerCustom, QsciAPIs
import re


class MyLexer(QsciLexerCustom):
    def __init__(self, parent):
        super(MyLexer, self).__init__(parent)
        # Default text settings
        # ----------------------
        self.setDefaultColor(QColor("#CCCCCC"))
        self.setDefaultPaper(QColor("#201c1c"))
        self.setDefaultFont(QFont("Cascadia Code", 10))
    
        # Initialize colors per style
        # ----------------------------
        self.setColor(QColor("#CCCCCC"), 0)   # Style 0: white
        self.setColor(QColor("#C586C0"), 1)   # Style 1: pink
        self.setColor(QColor("yellow"), 2)    # Style 2: blue
        self.setColor(QColor("#6A9955"), 3)   # Style 3: green
        self.setColor(QColor("#CE9178"), 4)   # Style 4: orange (strings)
        self.setColor(QColor("#569CD6"), 5)   # blue (functions, classes etc)
        self.setColor(QColor("#4EC9B0"), 6)   # green (functions, classes name)

        # Initialize paper colors and fonts per style
        # ----------------------------------
        for i in range(6):
            self.setPaper(QColor("#201c1c"), i)
            self.setFont(QFont("Cascadia Code", 10, weight=QFont.Bold), i)


    def language(self):
        return "ScriptCreator"

    def description(self, style):
        if style == 0:
            return "myStyle_0"
        elif style == 1:
            return "myStyle_1"
        elif style == 2:
            return "myStyle_2"
        elif style == 3:
            return "myStyle_3"
        elif style == 4:
            return "myStyle_4"
        elif style == 5:
            return "myStyle_5"
        elif style == 6:
            return "myStyle_6"
        ###
        return ""

    def styleText(self, start, end):
        # 1. Initialize the styling procedure
        # ------------------------------------
        self.startStyling(start)

        # 2. Slice out a part from the text
        # ----------------------------------
        text = self.parent().text()[start:end]

        # 3. Tokenize the text
        # ---------------------
        p = re.compile(r"[*]\/|\/[*]|\s+|\w+|\W")

        # 'token_list' is a list of tuples: (token_name, token_len)
        token_list = [ (token, len(bytearray(token, "utf-8"))) for token in p.findall(text)]

        # 4. Style the text
        # ------------------
        # 4.1 Check if multiline comment
        comment_flag = False
        string_flag = False
        classAndFuncName_flag = False
        classOrFuncName = ""
        editor = self.parent()
        if start > 0:
            previous_style_nr = editor.SendScintilla(editor.SCI_GETSTYLEAT, start - 1)
            if previous_style_nr == 3:
                comment_flag = True
        # 4.2 Style the text in a loop
        for i, token in enumerate(token_list):
            if comment_flag:
                if "\n" in token[0]:
                    comment_flag = False
                else:
                    self.setStyling(token[1], 3)
            elif string_flag:
                if '"' in token[0]:
                    string_flag = False
                    self.setStyling(token[1], 4)
                else:
                    self.setStyling(token[1], 4)
            elif classAndFuncName_flag:
                if "\n" in token[0]:
                    classAndFuncName_flag = False
                    self.setStyling(token[1], 6)
                else:
                    if token[0] in ["(", ")", "{", "}", "[", "]"]:
                        self.setStyling(token[1], 2)
                        if token[0] == ")":
                            #print(classOrFuncName)
                            #print(i)
                            pass
                    else:
                        self.setStyling(token[1], 6)
                        classOrFuncName = token[0]
            else:
                if token[0] in ["for", "while", "return", "in", "break", "pass", "if", "import"]:
                    self.setStyling(token[1], 1)
                elif token[0] in ["(", ")", "{", "}", "[", "]"]:
                    self.setStyling(token[1], 2)
                elif token[0] == "#":
                    comment_flag = True
                    self.setStyling(token[1], 3)
                elif token[0] == '"':
                    string_flag = True
                    self.setStyling(token[1], 4)
                elif token[0] in ["def", "class", "not", "True", "False", "self"]:
                    self.setStyling(token[1], 5)
                    if token[0] in ["class", "def"]:
                        classAndFuncName_flag = True
                else:
                    # Default style
                    if not comment_flag and not string_flag:
                        self.setStyling(token[1], 0)

    def autocompletion(self, parent, text):
        parent.autocompletions.append(text)
        for ac in parent.autocompletions:
            parent.api.add(ac)

        ## Compile the api for use in the lexer
        parent.api.prepare()

class TextEdit(QsciScintilla):
    ARROW_MARKER_NUM = 8

    def __init__(self, parent=None):
        super(TextEdit, self).__init__(parent)

        # tab indent
        self.setTabWidth(4)

        # caret settings
        self.setCaretForegroundColor(QColor("white"))
        self.setCaretWidth(2)

        # font ?
        font = QFont("Cascadia Code", 10)

        # Set the stylesheet for the vertical scrollbar
        self.verticalScrollBar().setStyleSheet('''
            QTableWidget {
                background-color: rgb(32, 28, 28);
                color: rgb(255, 255, 255);
            }
        
            /* VERTICAL SCROLLBAR */
            QScrollBar:vertical {
                border: none;
                background: rgb(32, 28, 28);
                width: 14px;
            }
        
            /* HANDLE BAR VERTICAL */
            QScrollBar::handle:vertical {
                background-color: rgb(82, 81, 81);
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgb(148, 148, 148);
            }
        
            /* HIDE ARROWS */
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                image: none;
                background: rgb(32, 28, 28);
                                    
            }
        
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: rgb(32, 28, 28);
            }
        ''')
        self.horizontalScrollBar().setStyleSheet('''
            QTableWidget {
                background-color: rgb(32, 28, 28);
                color: rgb(255, 255, 255);
            }
        
            /* HORIZONTAL SCROLLBAR */
            QScrollBar:horizontal {
                border: none;
                background: rgb(32, 28, 28);
                height: 14px;
            }
        
            /* HANDLE BAR HORIZONTAL */
            QScrollBar::handle:horizontal {
                background-color: rgb(82, 81, 81);
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: rgb(148, 148, 148);
            }
        
            /* HIDE ARROWS */
            QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
                image: none;
                background: rgb(32, 28, 28);
            }
        
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: rgb(32, 28, 28);
            }
        ''')

        # Margin 0 is used for line numbers
        fontmetrics = QFontMetrics(font)
        self.setMarginsFont(font)
        self.setMarginWidth(0, fontmetrics.width("00") + 10)
        self.setMarginLineNumbers(0, True)
        self.setMarginsForegroundColor(QColor("#edebeb"))
        self.setMarginsBackgroundColor(QColor(32, 28, 28))

        self.setMarginWidth(1, "00")
        self.setMarginBackgroundColor(0, QColor("red"))


        lexer = MyLexer(self)

        ## Create an API for us to populate with our autocomplete terms
        self.api = QsciAPIs(lexer)

        self.autocompletions = [
            "def",
            "class",
            "not",
            "for",
            "if",
            "while",
            "False",
            "True",
        ]
        for ac in self.autocompletions:
            self.api.add(ac)

        ## Compile the api for use in the lexer
        self.api.prepare()

        # apply lexer
        self.setLexer(lexer)
        self.setAutoCompletionThreshold(1)
        self.setAutoCompletionSource(QsciScintilla.AcsAPIs)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        text = bytearray(str.encode("Arial"))      
        self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, 1, text)

    def keyPressEvent(self, event):
        key = event.text()

        def _replace(self, replace):
            # Save the current position
            current_pos = self.getCursorPosition()

            # Insert the characters into the editor
            self.replaceSelectedText(replace)
            self.setCursorPosition(current_pos[0], current_pos[1] + 1)

        if key == "(":
            replace = "()"
            _replace(self, replace)
        elif key == "[":
            replace = "[]"
            _replace(self, replace)
        elif key == "{":
            replace = "{}"
            _replace(self, replace)
        else:
            # Call the base class implementation for other key presses
            super().keyPressEvent(event)

    def on_margin_clicked(self, nmargin, nline, modifiers):
        # Toggle marker for the line the margin was clicked on
        if self.markersAtLine(nline) != 0:
            self.markerDelete(nline, self.ARROW_MARKER_NUM)
        else:
            self.markerAdd(nline, self.ARROW_MARKER_NUM)

