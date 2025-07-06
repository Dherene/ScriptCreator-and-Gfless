import re
import keyword
import builtins
import types
import json
import importlib

from PyQt5.Qsci import QsciLexerCustom, QsciScintilla
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

# config type
DefaultConfig = dict[str, str, tuple[str, int]]

class NeutronLexer(QsciLexerCustom):
    """Base Custo Lexer class for all language"""

    def __init__(self, language_name, editor, theme=None, defaults: DefaultConfig = None):
        super(NeutronLexer, self).__init__(editor)

        self.editor = editor
        editor.SendScintilla(editor.SCI_STYLESETHOTSPOT, 13, True)
        editor.SCN_HOTSPOTCLICK.connect(self.showPlayerClass)
        self.language_name = language_name
        self.theme_json = None
        if theme is None:
            self.theme = "src/theme.json"
        else:
            self.theme = theme

        self.token_list: list[str, str] = []

        self.keywords_list = []
        self.builtin_names = []

        if defaults is None:
            defaults: DefaultConfig = {}
            defaults["color"] = "#abb2bf"
            defaults["paper"] = "#201c1c"
            defaults["font"] = ("Cascadia Code", 10)

        # Default text settings
        self.setDefaultColor(QColor(defaults["color"]))
        self.setDefaultPaper(QColor(defaults["paper"]))
        self.setDefaultFont(QFont(defaults["font"][0], defaults["font"][1]))

        self._init_theme_vars()
        self._init_theme()

    def showPlayerClass(self):
        from editor import PlayerDialog
        player_dialog = PlayerDialog()
        player_dialog.exec_()

    def setKeywords(self, keywords: list[str]):
        """Set List of strings that considered keywords for this language."""
        self.keywords_list = keywords

    def setBuiltinNames(self, buitin_names: list[str]):
        """Set list of builtin names"""
        self.builtin_names = buitin_names

    def _init_theme_vars(self):
        # color per style

        self.DEFAULT = 0
        self.KEYWORD = 1
        self.TYPES = 2
        self.STRING = 3
        self.KEYARGS = 4
        self.BRACKETS_1 = 5
        self.BRACKETS_2 = 6
        self.BRACKETS_3 = 7
        self.COMMENTS = 8
        self.CONSTANTS = 9
        self.FUNCTIONS = 10
        self.CLASSES = 11
        self.FUNCTION_DEF = 12
        self.PLAYER = 13
        self.CLASS_AND_FUNC = 14
        self.OPERATORS = 15

        self.default_names = [
            "default",
            "keyword",
            "types",
            "string",
            "keyargs",
            "brackets_1",
            "brackets_2",
            "brackets_3",
            "comments",
            "constants",
            "functions",
            "classes",
            "function_def",
            "player",
            "class_and_func",
            "operators"
        ]

        self.font_weights = {
            "thin": QFont.Thin,
            "extralight": QFont.ExtraLight,
            "light": QFont.Light,
            "normal": QFont.Normal,
            "medium": QFont.Medium,
            "demibold": QFont.DemiBold,
            "bold": QFont.Bold,
            "extrabold": QFont.ExtraBold,
            "black": QFont.Black,
        }

    def _init_theme(self):
        with open(self.theme, "r") as f:
            self.theme_json = json.load(f)

        colors = self.theme_json["theme"]["syntax"]

        for clr in colors:
            name: str = list(clr.keys())[0]

            if name not in self.default_names:
                print(f"Theme error: {name} is not a valid style name")
                continue
            
            for k, v in clr[name].items():
                if k == "color":
                    self.setColor(QColor(v), getattr(self, name.upper()))
                elif k == "paper-color":
                    self.setPaper(QColor(v), getattr(self, name.upper()))
                elif k == "font":
                    try:
                        self.setFont(
                            QFont(
                                v.get("family", "Cascadia Code"), 
                                v.get("font-size", 10),
                                self.font_weights.get(v.get("font-weight", QFont.Normal)),
                                v.get("italic", False)
                            ),
                            getattr(self, name.upper())
                        )    
                    except AttributeError as e:
                        print(f"theme error: {e}")
            
    def language(self) -> str:
        return self.language_name

    def description(self, style: int) -> str:
        if style == self.DEFAULT:
            return "DEFAULT"
        elif style == self.KEYWORD:
            return "KEYWORD"
        elif style == self.TYPES:
            return "TYPES"
        elif style == self.STRING:
            return "STRING"
        elif style == self.KEYARGS:
            return "KEYARGS"
        elif style == self.BRACKETS_1:
            return "BRACKETS_1"
        elif style == self.BRACKETS_2:
            return "BRACKETS_2"
        elif style == self.BRACKETS_3:
            return "BRACKETS_3"
        elif style == self.COMMENTS:
            return "COMMENTS"
        elif style == self.CONSTANTS:
            return "CONSTANTS"
        elif style == self.FUNCTIONS:
            return "FUNCTIONS"
        elif style == self.CLASSES:
            return "CLASSES"
        elif style == self.FUNCTION_DEF:
            return "FUNCTION_DEF"
        elif style == self.PLAYER:
            return "PLAYER"
        elif style == self.CLASS_AND_FUNC:
            return "CLASS_AND_FUNC"
        elif style == self.OPERATORS:
            return "OPERATORS"

        return ""

    def generate_token(self, text):
        # 3. Tokenize the text 
        # ---------------------
        p = re.compile(r"[*]\/|\/[*]|\s+|[\w.]+|\W")

        # 'token_list' is a list of tuples: (token_name, token_len), ex: '(class, 5)' 
        self.token_list =  [ (token, len(bytearray(token, "utf-8"))) for token in p.findall(text)]

    def next_tok(self, skip: int = None):
        if len(self.token_list) > 0:
            if skip is not None and skip != 0:
                for _ in range(skip-1):
                    if len(self.token_list) > 0:
                        self.token_list.pop(0)
            return self.token_list.pop(0)
        else:
            return None

    def peek_tok(self, n=0):
        try:
            return self.token_list[n]
        except IndexError:
            return ['']

    def skip_spaces_peek(self, skip=None):
        """find he next non-space token but using peek without consuming it"""
        i = 0
        tok = " "
        if skip is not None:
            i = skip
        while tok[0].isspace():
            tok = self.peek_tok(i)
            i += 1
        return tok, i
    
    def find_line(self, start, end):
        text = self.editor.text()
        text_lines = text.split('\n')

        lines = [[1, 0, len(text_lines[0])]]

        for i in range(1, len(text_lines)):
            lines.append([i+1,lines[i-1][2], len(text_lines[i])+lines[i-1][2]+1])
        
        start_adding = False
        editing_lines = []

        for line in lines:
            line_number, line_start, line_end = line

            # Check for overlap
            if (line_start <= end and line_end >= start):
                editing_lines.append(line_number)

        #print(f"Currently styled lines: {editing_lines}")

    
class PyCustomLexer(NeutronLexer):
    """Custom lexer for python"""

    def __init__(self, editor):
        super(PyCustomLexer, self).__init__("Python", editor)

        # used to keep track of real module names so every module doesnt have to be tested every time
        self.real_modules = []
        self.fake_modules = []
        self.setKeywords(keyword.kwlist)
        self.setBuiltinNames([
            name
            for name, obj in vars(builtins).items()
            if isinstance(obj, types.BuiltinFunctionType)
        ])

    def styleText(self, start: int, end: int) -> None:
        # 1. Start styling procedure
        self.startStyling(start)

        # 2. Slice out part from the text
        text = self.editor.text()[start:end]

        # 3. Tokenize the text
        self.generate_token(text)

        def _check_if_module(name):
            if name in self.real_modules:
                return True
            if name in self.fake_modules:
                return False
            try:
                importlib.import_module(name)
                self.real_modules.append(name)
                return True
            except Exception as e:
                self.fake_modules.append(name)
                return False

        # Flags
        string_flag = False
        string_brackets_flag = False
        comment_flag = False
        bracket_depth = 1  # Track the bracket depth

        if start > 0:
            prev_style = self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, start -1)
            if prev_style == self.COMMENTS:
                comment_flag = False

        while True:
            curr_token = self.next_tok()

            if curr_token is None:
                break

            tok: str = curr_token[0]
            tok_len: int = curr_token[1]

            if comment_flag:
                self.setStyling(tok_len, self.COMMENTS)
                if "\n" in tok:
                    comment_flag = False
                continue
            if string_flag:
                if tok == '"' or tok == "'":
                    string_flag = False
                    self.setStyling(tok_len, self.STRING)
                elif tok in ["(", "{", "["]:
                    self.setStyling(tok_len, self.BRACKETS_1)
                    string_brackets_flag = True
                elif tok in [")", "}", "]"]:
                    self.setStyling(tok_len, self.BRACKETS_1)
                    string_brackets_flag = False
                elif string_brackets_flag:
                    if tok == "player":
                        self.setStyling(tok_len, self.PLAYER)
                    else:
                        self.setStyling(tok_len, self.DEFAULT)
                else:
                    self.setStyling(tok_len, self.STRING)
                continue
            if tok in self.editor.defined_classes:
                self.setStyling(tok_len, self.CLASSES)
            elif tok in self.editor.defined_funcs:
                self.setStyling(tok_len, self.FUNCTIONS)
            elif tok in self.editor.imported_modules:
                self.setStyling(tok_len, self.CLASSES)
            elif tok == "class":
                name, ni = self.skip_spaces_peek()
                brac_or_colon, _ = self.skip_spaces_peek(ni)
                if name[0].isidentifier() and brac_or_colon[0] in (":", "("):
                    self.setStyling(tok_len, self.CLASS_AND_FUNC)
                    _ = self.next_tok(ni)
                    self.setStyling(name[1]+1, self.CLASSES)
                    continue
                else:
                    self.setStyling(tok_len, self.KEYWORD)
                    continue
            elif tok == "def":
                name, ni = self.skip_spaces_peek()
                if name[0].isidentifier():
                    self.setStyling(tok_len, self.CLASS_AND_FUNC)
                    _ = self.next_tok(ni)
                    self.setStyling(name[1]+1, self.FUNCTION_DEF)
                    continue
                else:
                    self.setStyling(tok_len, self.KEYWORD)
                    continue
            elif tok in ["False", "None", "True", "End", "is", "lambda", "or", "f"]:
                self.setStyling(tok_len, self.CLASS_AND_FUNC)
            elif tok in self.keywords_list:
                self.setStyling(tok_len, self.KEYWORD)
            elif tok.strip() == "." and self.peek_tok()[0].isidentifier():
                self.setStyling(tok_len, self.DEFAULT)
                curr_token = self.next_tok()
                tok: str = curr_token[0]
                tok_len: int = curr_token[1]
                if self.peek_tok()[0] == "(":
                    self.setStyling(tok_len, self.FUNCTIONS)
                else:
                    self.setStyling(tok_len, self.DEFAULT)
                continue
            elif tok.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
            elif tok in ["(", "{", "["]:
                cur_bracket = bracket_depth%3
                if cur_bracket == 1:
                    self.setStyling(tok_len, self.BRACKETS_1)
                elif cur_bracket == 2:
                    self.setStyling(tok_len, self.BRACKETS_2)
                else:
                    self.setStyling(tok_len, self.BRACKETS_3)
                bracket_depth += 1
            elif tok in [")", "}", "]"]:
                bracket_depth -= 1
                cur_bracket = bracket_depth%3
                if cur_bracket == 1:
                    self.setStyling(tok_len, self.BRACKETS_1)
                elif cur_bracket == 2:
                    self.setStyling(tok_len, self.BRACKETS_2)
                else:
                    self.setStyling(tok_len, self.BRACKETS_3)
            elif tok == '"' or tok == "'":
                self.setStyling(tok_len, self.STRING)
                string_flag = True
            elif tok == "#":
                self.setStyling(tok_len, self.COMMENTS)
                comment_flag = True
            elif tok in self.builtin_names:
                self.setStyling(tok_len, self.TYPES)
            elif tok in["player", "alt"]:
                self.setStyling(tok_len, self.PLAYER)
            elif tok in ['+', '-', '*', '/', '%', '=', '<', '>', "!=", ">=", "=>", "<=", "=<", "=="]:
                self.setStyling(tok_len, self.OPERATORS)
            #elif _check_if_module(tok):
            #    self.setStyling(tok_len, self.CLASSES)
            else:
                self.setStyling(tok_len, self.DEFAULT)
