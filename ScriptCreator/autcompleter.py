from PyQt5.Qsci import QsciAPIs
from player import Player
import importlib
import builtins
from pathlib import Path

class AutoCompleter():
    def __init__(self, api):
        self.api: QsciAPIs = api
        self.completions_names = []
        
        self.line = 0
        self.index = 0
        self.text = ""
        self.current = ""
    
    def player_completions(self):
        try:
            if self.current != "player":
                methods = [method_name for method_name in dir(Player())
                  if callable(getattr(Player(), method_name))]
                variables = Player().__dict__.keys()
                self.load_autocomplete(methods, variables)
                self.current = "player"
        except Exception as e:
            print(f"{e}")

    def other_competions(self, module_name):
        #try import
        all_methods = []
        if self.current != module_name:
            try:
                module = importlib.import_module(module_name)
                #print(f"{module_name} is a module")
                try:
                    all_methods = [*all_methods, *module.__all__]
                except:
                    all_methods = [*all_methods, *dir(module)]

                try:
                    for mod in module.__loader__.get_resource_reader().contents():
                        if mod.endswith((".py", ".pyc", ".pyd")) and not mod.startswith("_") and "." not in Path(mod).stem:
                            all_methods.append(Path(mod).stem)
                except:
                    pass
            except Exception as e:
                #print(f"{module_name} is not a module")
                return False
            self.load_autocomplete(all_methods, [])
            self.current = module_name
        return True
    
    def get_builtins(self, user_defined_methods = [], user_defined_vars = []):
        try:
            if self.current != [*user_defined_methods, *user_defined_vars]:
                builtin_methods = dir(builtins)
                self.load_autocomplete([*builtin_methods, *user_defined_methods], user_defined_vars)
                self.current =  [*user_defined_methods, *user_defined_vars]
        except Exception as e:
            print(f"{e}")

    def array_methods(self):
        try:
            if self.current != "array":
                methods = dir([])
                self.load_autocomplete(methods, [])
                self.current = "array"
        except Exception as e:
            print(f"{e}")

    def string_methods(self):
        try:
            if self.current != "string":
                methods = dir(str)
                self.load_autocomplete(methods, [])
                self.current = "string"
        except Exception as e:
            print(f"{e}")

    def int_methods(self):
        try:
            if self.current != "int":
                methods = dir(int)
                self.load_autocomplete(methods, [])
                self.current = "int"
        except Exception as e:
            print(f"{e}")

    def load_autocomplete(self, methods, variables):
        self.api.clear()
        #[self.api.add(f"{i}?0") for i in methods]
        #[self.api.add(f"{i}?1") for i in variables]
        [self.api.add(f"{i}") for i in methods]
        [self.api.add(f"{i}") for i in variables]
        self.api.prepare() 



        

