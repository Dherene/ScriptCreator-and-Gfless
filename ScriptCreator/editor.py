from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.Qsci import * 

from pathlib import Path
from lexer import PyCustomLexer
from autcompleter import AutoCompleter
from typing import TYPE_CHECKING
import re
import importlib
import inspect
import builtins

if TYPE_CHECKING:
    from main import MyWindow

class Editor(QsciScintilla):
    
    def __init__(self, main_window, parent=None):
        super(Editor, self).__init__(parent)

        # Set the stylesheet for scrollbars
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

        self.main_window: MyWindow = main_window

        # user defined variables and methods
        self.imported_modules = []
        self.defined_arrays = []
        self.defined_integers = []
        self.defined_strings = []
        self.defined_funcs = []
        self.defined_classes = []
        self.defined_other_vars = []
        # EDITOR
        #self.cursorPositionChanged.connect(self._cusorPositionChanged)        
        #self.textChanged.connect(self._textChanged)

        # encoding
        self.setUtf8(True)
        # Font
        self.window_font = QFont("Cascadia Code") # font needs to be installed in your computer (should come as default with windows)
        self.window_font.setPointSize(10)
        self.setFont(self.window_font)

        # brace matching
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)
        self.setMatchedBraceBackgroundColor(QColor("#47577a"))

        # brace notmatching
        self.setUnmatchedBraceBackgroundColor(QColor("#47577a"))


        # indentation
        self.setIndentationGuides(True)
        self.setTabWidth(4)
        self.setIndentationsUseTabs(True)
        self.setAutoIndent(True)

        # autocomplete
        self.setAutoCompletionSource(QsciScintilla.AcsAPIs)
        self.setAutoCompletionThreshold(1) 
        self.setAutoCompletionCaseSensitivity(False)
        self.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

        # doesnt work as expected
        # doesnt show for functions inside methods
        # call tips
        #self.setCallTipsStyle(QsciScintilla.CallTipsNoContext)
        #self.setCallTipsVisible(0)

        # doesnt work as expected
        # moves location of the autocomplete window seemingly to random position
        # register images
        #fnc_img = QPixmap("src/fnc_img.png")
        #var_img = QPixmap("src/var_img.png")
        #self.registerImage(0, fnc_img)
        #self.registerImage(1, var_img)

        # wrap mode
        # using wrap mode instead of horizontal scrollbar due to known issue with QScintilla
        # https://github.com/jacobslusser/ScintillaNET/issues/216
        self.setWrapMode(QsciScintilla.WrapWhitespace)

        # caret settings
        self.setCaretForegroundColor(QColor("white"))
        self.setCaretWidth(2)
        
        # EOL
        self.setEolMode(QsciScintilla.EolWindows)
        self.setEolVisibility(False)

        # lexer
        self.pylexer = PyCustomLexer(self) 
        self.pylexer.setDefaultFont(self.window_font)

        self.__api = QsciAPIs(self.pylexer)

        self.auto_completer = AutoCompleter(self.__api)

        self.setLexer(self.pylexer)

        #every script should start with this code
        self.setText("""import gfless_api
# Gets current player object
player = self.players[self.tab_widget.currentIndex()][0]

# Get pidnum = (PID number)
pidnum = player.PIDnum

# Gets all The players and remove current player to get alts
alts = [sublist[0] if sublist[0] is not None else None for sublist in self.players]
alts.remove(player)

""")

        # line numbers
        self.setMarginType(0, QsciScintilla.NumberMargin)
        self.setMarginWidth(0, "0000")
        self.setMarginsForegroundColor(QColor("#ff888888"))
        self.setMarginsBackgroundColor(QColor("#201c1c"))
        self.setMarginsFont(self.window_font)
    
    def parseDocument(self, text):
        # clear the arrays
        # user defined variables and methods
        self.imported_modules = []
        self.defined_arrays = []
        self.defined_integers = []
        self.defined_strings = []
        self.defined_funcs = []
        self.defined_classes = []
        self.defined_other_vars = []


        # Define the patterns
        array_pattern = r'(\w+)\s*=\s*\[.*\]'
        string_pattern = r'(\w+)\s*=\s*\".*\"'
        int_pattern = r'(\w+)\s*=\s*(\d+)'
        instance_array_pattern = r'self\.(\w+)\s*=\s*\[.*\]'
        instance_string_pattern = r'self\.(\w+)\s*=\s*\".*\"'
        instance_int_pattern = r'self\.(\w+)\s*=\s*(\d+)'
        func_pattern = r"(def)\s(\w+)\([a-zA-Z0-9_:\[\]=, ]*\)"
        class_pattern = r"(class)\s(\w+)\([a-zA-Z0-9_:\[\]=, ]*\)"
        other_var_pattern = r'(\w+)\s*=\s*'
        from_import_pattern = r'from\s+(\w+)\s+import\s+([a-zA-Z0-9_,\s]+)'
        import_pattern = r'import\s+([a-zA-Z0-9_,.\s]+)'
        

        # Split the text into lines using the newline character '\n'
        lines = text.split('\n')
    
        # Iterate through each line and check if it matches any of the patterns
        for line in lines:
            line = line.lstrip()
            array_match = re.match(array_pattern, line)
            string_match = re.match(string_pattern, line)
            int_match = re.match(int_pattern, line)
            instance_array_match = re.match(instance_array_pattern, line)
            instance_string_match = re.match(instance_string_pattern, line)
            instance_int_match = re.match(instance_int_pattern, line)

            func_match = re.match(func_pattern, line)
            class_match = re.match(class_pattern, line)

            other_var_match = re.match(other_var_pattern, line)
            import_match = re.match(import_pattern, line)
            from_import_match = re.match(from_import_pattern, line)

            if array_match:
                variable_name = array_match.group(1)
                if variable_name not in self.defined_arrays:
                    self.defined_arrays.append(variable_name)
            elif instance_array_match:
                variable_name = instance_array_match.group(1)
                if variable_name not in self.defined_arrays:
                    self.defined_arrays.append(variable_name)
            elif string_match:
                variable_name = string_match.group(1)
                if variable_name not in self.defined_strings:
                    self.defined_strings.append(variable_name)
            elif instance_string_match:
                variable_name = instance_string_match.group(1)
                if variable_name not in self.defined_strings:
                    self.defined_strings.append(variable_name)
            elif int_match:
                variable_name = int_match.group(1)
                if variable_name not in self.defined_integers:
                    self.defined_integers.append(variable_name)
            elif instance_int_match:
                variable_name = instance_int_match.group(1)
                if variable_name not in self.defined_integers:
                    self.defined_integers.append(variable_name)
            elif func_match:
                variable_name = func_match.group(2)
                if variable_name not in self.defined_funcs:
                    self.defined_funcs.append(variable_name)
            elif class_match:
                variable_name = class_match.group(2)
                if variable_name not in self.defined_classes:
                    self.defined_classes.append(variable_name)
            elif other_var_match:
                variable_name = other_var_match.group(1)
                if variable_name not in self.defined_other_vars:
                    self.defined_other_vars.append(variable_name)
            elif import_match:
                imported_names = import_match.group(1).split(',')
                #print(imported_names)
                for imported_name in imported_names:
                    imported_name = imported_name.strip()
                    if imported_name not in self.imported_modules:
                        try:
                            importlib.import_module(imported_name)
                            self.imported_modules.append(imported_name)
                            #print(self.imported_modules)
                        except:
                            pass
            elif from_import_match:
                module_name = from_import_match.group(1)
                imported_names = from_import_match.group(2).split(',')
                for imported_name in imported_names:
                    imported_name = imported_name.strip()
                    if imported_name not in [*self.defined_funcs, *self.defined_classes, *self.imported_modules]:
                        self.get_object_type_from_module(module_name, imported_name)

            else:
                # maybe something else ?
                # perhaps change style to indicate error ?
                pass

    def validateDocument(self, text):
        try:
            code = compile(text, filename='<string>', mode='exec')
            code_symbols = code.co_names
            undefined_variables = []
            local_vars = []

            for symbol in code_symbols:
                local_vars.append(symbol)

            # Check if all used variables are defined in builtins or locals
            for var in code_symbols:
                if var not in builtins.__dict__ and var not in local_vars:
                    undefined_variables.append(var)
            if not undefined_variables:
                return True
            else:
                #print(f"Undefined variables: {', '.join(undefined_variables)}")
                return False
        except SyntaxError as e:
            print(f"SyntaxError: {e}")
            return False


    def get_object_type_from_module(self, module_name, object_name):
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                return "module not found"
            
            if module_name not in self.imported_modules:
                self.imported_modules.append(module_name)
                #print(self.imported_modules)
            
            #print(f"{module_name}.{object_name}")
            spec2 = importlib.util.find_spec(f"{module_name}.{object_name}")
            if spec2 is not None:
                if f"{module_name}.{object_name}" not in self.imported_modules:
                    self.imported_modules(f"{module_name}.{object_name}")
                    #print(self.imported_modules)

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, object_name):
                obj = getattr(module, object_name)
                if inspect.isclass(obj):
                    if object_name not in self.defined_classes:
                        self.defined_classes.append(object_name)
                    return "class"
                elif inspect.isfunction(obj):
                    if object_name not in self.defined_funcs:
                        self.defined_funcs.append(object_name)
                else:
                    return "unknown"
            else:
                return "object not found"

        except Exception as e:
            return f"Error: {str(e)}"

    def keyPressEvent(self, e: QKeyEvent) -> None:          
        #self.parseDocument(text=self.text())
        #self.validateDocument(text=self.text())
        key_pressed = False

        if e.key() == Qt.Key_Return:
            key_pressed = True
            super().keyPressEvent(e)

            # Get the current line and check if it ends with ":"
            current_line = self.text(self.getCursorPosition()[0]-1)
            if current_line.strip().endswith(":"):
                # Insert a tab
                self.insert('\t')

                # Move the cursor to the next position
                current_pos = self.getCursorPosition()
                self.setCursorPosition(current_pos[0], current_pos[1] + 1)

        def _replace(replace):
            # Save the current position
            current_pos = self.getCursorPosition()

            # Insert the characters into the editor
            self.insert(replace)
            self.setCursorPosition(current_pos[0], current_pos[1] + len(replace) - 1)

        def _extract_word_before_dot(s):
            match = re.search(r'(\w+)\.', s)
            if match:
                return match.group(1)
            return None
        
        def _extract_full_method_name(s, pop_it = True):
            splitted_method_name = s.split()[-1].split(".")
            if pop_it:
                if len(splitted_method_name) > 1:
                    splitted_method_name.pop(-1)
            return ".".join(splitted_method_name)

        key = e.text()

        if key == "(":
            replace = "()"
            _replace(replace)
        elif key == "[":
            replace = "[]"
            _replace(replace)
        elif key == "{":
            replace = "{}"
            _replace(replace)
        elif key == '"':
            replace = '""'
            _replace(replace)
        else:
            if not key_pressed:
                super().keyPressEvent(e)
                self.parseDocument(text=self.text())
            try:
                c_pos = self.getCursorPosition()
                text = self.text(c_pos[0])[:c_pos[1]]
                #if "." in text and "import" in text:
                #    print(text)
                split_text = text.split()
                try:
                    if split_text[0] == "from":
                        if len(split_text) >= 2:
                            if split_text[2] == "import":
                                method_name = split_text[1]
                                self.auto_completer.other_competions(_extract_full_method_name(method_name, False))
                                self.get_object_type_from_module(method_name, split_text[3])
                except:
                    if "." in text:
                        method_name = _extract_word_before_dot(text)
                        if method_name in ["player", "alt"]:
                            self.auto_completer.player_completions()
                        elif method_name in self.defined_arrays:
                            self.auto_completer.array_methods()
                        elif method_name in self.defined_strings:
                            self.auto_completer.string_methods()
                        elif method_name in self.defined_integers:
                            self.auto_completer.int_methods()
                        else:
                            if not self.auto_completer.other_competions(_extract_full_method_name(text, True)):
                                #print("get builtins instead")
                                self.auto_completer.get_builtins(user_defined_methods=[*self.defined_funcs, *self.defined_classes], user_defined_vars=[*self.defined_arrays, *self.defined_strings, *self.defined_integers, *self.defined_other_vars])      
                else:
                    self.auto_completer.get_builtins(user_defined_methods=[*self.defined_funcs, *self.defined_classes], user_defined_vars=[*self.defined_arrays, *self.defined_strings, *self.defined_integers, *self.defined_other_vars])
            except Exception as exc:
                print(f"{exc}")
                self.auto_completer.get_builtins(user_defined_methods=[*self.defined_funcs, *self.defined_classes], user_defined_vars=[*self.defined_arrays, *self.defined_strings, *self.defined_integers, *self.defined_other_vars])
    
    def loaded_autocomplete(self):
        pass

# this should ideally be moved to seperate module to not polute editor.py, 
# but issue arises with circular import, since this is called from lexer.py
class PlayerDialog(QDialog):
    def __init__(self, parent=None):
        super(PlayerDialog, self).__init__(parent)

        self.setWindowIcon(QIcon('src/icon.png'))
        self.setWindowTitle("Show player module")
        self.setGeometry(400, 100, 800, 800)

        # Set up the layout
        layout = QVBoxLayout(self)

        # Create an instance of your Editor class
        self.editor = Editor(main_window=None, parent=self)

        try:
            # Import the player module dynamically
            player_module = importlib.import_module("player")
            player_source_code = inspect.getsource(player_module)
        except Exception as e:
            print(f"{e}")
            player_source_code = """# Failed to retrieve player.py source
            # This is most likely due to player.py missing in the %CD%/src directory
            """

        #player_source_code = ""
        ## Set the editor text to the source code of the player module
        self.editor.setText(player_source_code)

        # Set the editor as read-only
        #self.editor.setReadOnly(True)

        # Add the editor to the layout
        layout.addWidget(self.editor)

        # Add a button to close the dialog
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)


import sys

if __name__ == "__main__":
    app_name = 'Script Creator by Stradiveri'

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = PlayerDialog()
    window.show()
    sys.exit(app.exec_())
