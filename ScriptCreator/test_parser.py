import importlib.util
import inspect
import re
import time
import pkgutil

class Parser():
    def __init__(self) -> None:
        self.global_scope = {"depth": 0, "vars": [], "classes": [], "functions": [], "imported_classes": [], "imported_functions": [], "imported_modules": [], "scopes": []}
        self.imported_modules = []
        self.defined_arrays = []
        self.defined_integers = []
        self.defined_strings = []
        self.defined_funcs = []
        self.defined_classes = []
        self.defined_other_vars = []

        # Define the patterns
        self.array_pattern = r'(\w+)\s*=\s*\[.*\]'
        self.string_pattern = r'(\w+)\s*=\s*\".*\"'
        self.int_pattern = r'(\w+)\s*=\s*(\d+)'
        self.instance_array_pattern = r'self\.(\w+)\s*=\s*\[.*\]'
        self.instance_string_pattern = r'self\.(\w+)\s*=\s*\".*\"'
        self.instance_int_pattern = r'self\.(\w+)\s*=\s*(\d+)'
        self.func_pattern = r"(def)\s(\w+)\(([^)]*\"(?:\\\"|.)*?\"[^)]*|[^)]*)\):"
        self.class_pattern = r"(class)\s(\w+)[a-zA-Z0-9_:\[\]=, ]*"
        self.other_var_pattern = r'(\w+)\s*=\s*'
        self.instance_other_var_pattern = r'(?:self\.)?(\w+)\s*=\s*'
        self.from_import_pattern = r'from\s+(\w+)\s+import\s+([a-zA-Z0-9_,\s]+)'
        self.import_pattern = r'import\s+([a-zA-Z0-9_,.\s]+)'

    def check_module_or_class(self, name):
        try:
            # Check if the name is a class
            if name in globals() and inspect.isclass(globals()[name]):
                return ["class", {}]

            # Attempt to import as a module
            module = importlib.import_module(name)
            if inspect.ismodule(module):
                funcs = [name for name, obj in inspect.getmembers(module)
                  if callable(obj) and not inspect.isclass(obj)]
                class_names = [name for name, obj in inspect.getmembers(module)
                  if inspect.isclass(obj)]
                try:
                    submodules = [name for _, name, _ in pkgutil.iter_modules(module.__path__)]
                except:
                    submodules = []

                return ["module", {"name": name, "functions": funcs,"classes": class_names,"submodules": submodules}]

        except Exception as e:
            print(f"{e}")
            pass
        
        return [None]

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

    def split_lines_ignore_strings(self, text):
        lines = []
        current_line = ""
        in_string = False

        for char in text:
            if char == '"' and not in_string:
                in_string = True
                current_line += char
            elif char == '"' and in_string:
                in_string = False
                current_line += char
            elif char == '\n' and in_string:
                current_line += '0'
            elif char == '\n' and not in_string:
                #if not current_line.isspace(): 
                lines.append(current_line)
                current_line = ""
            else:
                current_line += char

        return lines

    def add_variable_to_scope(self, variable_name, var_type, current_scope):
        if not any(variable["name"] == variable_name for variable in current_scope["vars"]):
            current_scope["vars"].append({"name": variable_name, "type": var_type})

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

        current_scope = self.global_scope

        # Split the text into lines using the newline character '\n'
        # Split lines while ignoring \n within strings
        lines = self.split_lines_ignore_strings(text)

        # Iterate through each line and check if it matches any of the patterns
        for line in lines:
            cur_line_depth = 99
            if len(line) > 1:
                i = 0
                spaces = 0
                tabs = 0
                while True:
                    if line[i] == " ":
                        spaces += 1
                    elif line[i] == "\t":
                        tabs += 1
                    else:
                        break
                    if i+1 > len(line)-1:
                        break
                    else:
                        i += 1
                cur_line_depth = tabs + int(spaces/4)

            cur_scope_depth = current_scope["depth"]
            #print(f"cur_line: {cur_line_depth} scope_depth: {cur_scope_depth}")
            if cur_line_depth < current_scope["depth"]:
                current_scope = current_scope["parent_scope"]
                #print("jump out of scope")

            line = line.lstrip()
            array_match = re.match(self.array_pattern, line)
            string_match = re.match(self.string_pattern, line)
            int_match = re.match(self.int_pattern, line)
            instance_array_match = re.match(self.instance_array_pattern, line)
            instance_string_match = re.match(self.instance_string_pattern, line)
            instance_int_match = re.match(self.instance_int_pattern, line)
            func_match = re.match(self.func_pattern, line)
            class_match = re.match(self.class_pattern, line)
            other_var_match = re.match(self.other_var_pattern, line)
            instance_other_var_match = re.match(self.instance_other_var_pattern, line)
            import_match = re.match(self.import_pattern, line)
            from_import_match = re.match(self.from_import_pattern, line)

            if array_match:
                variable_name = array_match.group(1)
                self.add_variable_to_scope(variable_name, "array", current_scope)
            elif instance_array_match:
                variable_name = instance_array_match.group(1)
                self.add_variable_to_scope(variable_name, "array", current_scope)
                if current_scope["name"] == "__init__":
                    self.add_variable_to_scope(variable_name, "array", current_scope["parent_scope"])
            elif string_match:
                variable_name = string_match.group(1)
                self.add_variable_to_scope(variable_name, "str", current_scope)
            elif instance_string_match:
                variable_name = instance_string_match.group(1)
                self.add_variable_to_scope(variable_name, "str", current_scope)
                if current_scope["name"] == "__init__":
                    self.add_variable_to_scope(variable_name, "str", current_scope["parent_scope"])
            elif int_match:
                variable_name = int_match.group(1)
                self.add_variable_to_scope(variable_name, "int", current_scope)
            elif instance_int_match:
                variable_name = instance_int_match.group(1)
                self.add_variable_to_scope(variable_name, "int", current_scope)
                if current_scope["name"] == "__init__":
                    self.add_variable_to_scope(variable_name, "int", current_scope["parent_scope"])
            elif func_match:
                func_name = func_match.group(2)
                parameters = func_match.group(3)
                current_scope["functions"].append({"name": func_name, "parameters": parameters})
                #print(f"new def scope {func_name} parameters: {parameters}")
                new_scope = {"name": func_name, "depth": cur_line_depth+1, "vars": [], "classes": [], "functions": [], "imported_classes": [], "imported_functions": [], "imported_modules": [], "scopes": [], "parent_scope": current_scope}
                current_scope["scopes"].append(new_scope)
                current_scope = new_scope
            elif class_match:
                class_name = class_match.group(2)
                #print(f"new class scope {class_name}")
                current_scope["classes"].append({"name": class_name, "functions": dir})
                new_scope = {"name": class_name, "depth": cur_line_depth+1, "vars": [], "classes": [], "functions": [], "imported_classes": [], "imported_functions": [], "imported_modules": [], "scopes": [], "parent_scope": current_scope}
                current_scope["scopes"].append(new_scope)
                current_scope = new_scope
            elif other_var_match:
                variable_name = other_var_match.group(1)
                self.add_variable_to_scope(variable_name, "other", current_scope)
            elif instance_other_var_match:
                variable_name = instance_other_var_match.group(1)
                self.add_variable_to_scope(variable_name, "other", current_scope)
                if current_scope["name"] == "__init__":
                    self.add_variable_to_scope(variable_name, "other", current_scope["parent_scope"])
            elif import_match:
                imported_names = import_match.group(1).split(',')
                for imported_name in imported_names:
                    imported_name = imported_name.strip()
                    _import = self.check_module_or_class(imported_name)
                    if _import[0] == "module":
                        if not any(imported_module["name"] == imported_name for imported_module in current_scope["imported_modules"]):
                            current_scope["imported_modules"].append(_import[1])
            elif from_import_match:
                module_name = from_import_match.group(1)
                imported_names = from_import_match.group(2).split(',')
                #for imported_name in imported_names:
                #    imported_name = imported_name.strip()
                #    print(self.get_object_type_from_module(module_name, imported_name))
            else:
                # maybe something else ?
                # perhaps change style to indicate error ?
                pass


text = """import time
import json
import PyQt5.QtWidgets
import phoenix
import threading
from getports import returnCorrectPort
from path import loadMap, findPath
from calculatefieldlocation import calculate_field_location, calculate_point_B_position
#import random

from PyQt5 import QtWidgets

# player class which can be reused in other standalone apis
class Player:
    def __init__(self, name = None):
        # player info
        self.name = name
        self.id = 0
        self.pos_x = 0
        self.pos_y = 0
        self.map_id = 0
        self.level = 0
        self.champion_level = 0
        self.hp_percent = 0
        self.current_hp = 0
        self.max_hp = 0
        self.mp_percent = 0
        self.current_mp = 0
        self.max_mp = 0
        self.is_resting = 0

        # inventory
        self.equip = {}
        self.etc = {}
        self.gold = {}
        self.main = {}

        # skills
        self.skills = {}

        # map_entities
        self.items = []
        self.monsters = []
        self.npcs = []
        self.players = []

        # other
        self.map_changed = False

        # should move to shared class so map doesnt have to be loaded for each character individually
        self.map_array = []
        
        self.recv_packet_conditions = []
        self.send_packet_conditions = []
        self.periodical_conditions = []
        
        # initialize 100 empty attributes so user can use them as he wants
        for i in range(1, 50):
            setattr(self, f'attr{i}', 0)

        for i in range(51, 101):
            setattr(self, f'attr{i}', [])

        if name is not None:
            # initialize api
            self.port = returnCorrectPort(self.name)
            self.api = phoenix.Api(self.port)
            self.stop_script = False
            pl_thread = threading.Thread(target=self.packetlogger)
            pl_thread.setDaemon(True)
            pl_thread.start()

            t = threading.Thread(target=self.queries, args=[0.25, ])
            t.start()

            #start periodic conditions loop
            t_periodic_conds = threading.Thread(target=self.exec_periodic_conditions)
            t_periodic_conds.start()

    def packetlogger(self):
        while self.api.working():
            if not self.api.empty():
                msg = self.api.get_message()
                json_msg = json.loads(msg)
                if json_msg["type"] == phoenix.Type.packet_send.value:
                    packet = json_msg["packet"]
                    splitPacket = packet.split()
                    #print(f"[SEND]: {packet}")
                    if splitPacket[0] == "walk":
                        self.pos_x, self.pos_y = int(splitPacket[1]), int(splitPacket[2])
                    for i in range(len(self.send_packet_conditions)):
                        try:
                            if self.send_packet_conditions[i][2]:
                                t_send_packet_condition = threading.Thread(target=self.exec_send_packet_condition, args=[self.send_packet_conditions[i][1], packet, i, self.send_packet_conditions[i][0]])
                                t_send_packet_condition.start()
                        except:
                            pass
                if json_msg["type"] == phoenix.Type.packet_recv.value:
                    packet = json_msg["packet"]
                    splitPacket = packet.split()
                    #print(f"[RECV]: {packet}")
                    if splitPacket[0] == ("stat"):
                        self.current_hp = int(splitPacket[1])
                        self.max_hp = int(splitPacket[2])
                        self.current_mp = int(splitPacket[3])
                        self.max_mp = int(splitPacket[4])
                        self.hp_percent = int((self.current_hp/self.max_hp)*100)
                        self.mp_percent = int((self.current_mp/self.max_mp)*100)
                    if splitPacket[0] == ("c_info"):
                        self.name = splitPacket[1]
                        self.id = splitPacket[6]
                        self.sp = splitPacket[15]
                    if splitPacket[0] == ("at"):
                        self.pos_x, self.pos_y = int(splitPacket[3]), int(splitPacket[4])
                    if splitPacket[0] == ("cond"):
                        self.can_attack = bool(int(splitPacket[3]))
                        self.can_move = bool(int(splitPacket[4]))
                        self.speed = splitPacket[5]
                    if splitPacket[0] == ("c_map"):
                        if splitPacket[3] == "1":
                            t_q = threading.Thread(target=self.queries, args=[1.5, False, False, False, True, ])
                            t_q.start()
                            t_mp = threading.Thread(target=self.update_map_change)
                            t_mp.start()
                            self.map_id = int(splitPacket[2])
                            self.map_array = loadMap(self.map_id)
                    if splitPacket[0] == ("gold"):
                        self.gold = int(splitPacket[1])
                    if splitPacket[0] == ("lev"):
                        self.lvl = splitPacket[1]
                        self.lvl_xp_current = splitPacket[2]
                        self.job_lvl = splitPacket[3]
                        self.job_lvl_xp_current = splitPacket[4]
                        self.lvl_xp_max = splitPacket[5]
                        self.c_lvl_xp_current = splitPacket[9]
                        self.c_lvl = splitPacket[10]
                        self.c_lvl_xp_max = splitPacket[11]
                    if splitPacket[0] == ("ivn"):
                        self.api.query_inventory()
                    if splitPacket[0] == ("ski"):
                        self.api.query_skills_info()
                    if splitPacket[0] == ("get"):
                        for entry in self.items[:]: 
                            if entry['id'] == int(splitPacket[3]):
                                self.items.remove(entry)
                                break
                    if splitPacket[0] == ("out"):
                        entity_type = int(splitPacket[1])
                        entity_id = int(splitPacket[2])

                        if entity_type == 1:
                            for entry in self.players[:]: 
                                if entry['id'] == entity_id:
                                    self.players.remove(entry)
                                    break
                        if entity_type == 2:
                            for entry in self.npcs[:]: 
                                if entry['id'] == entity_id:
                                    self.npcs.remove(entry)
                                    break
                        if entity_type == 3:
                            for entry in self.monsters[:]: 
                                if entry['id'] == entity_id:
                                    self.monsters.remove(entry)
                                    break
                        if entity_type == 9:
                            for entry in self.items[:]: 
                                if entry['id'] == entity_id:
                                    self.items.remove(entry)
                                    break
                    if splitPacket[0] == ("mv"):
                        entity_type = int(splitPacket[1])
                        entity_id = int(splitPacket[2])
                        entity_x = int(splitPacket[3])
                        entity_y = int(splitPacket[4])

                        if entity_type == 1:
                            for entry in self.players[:]: 
                                if entry['id'] == entity_id:
                                    entry["x"] = entity_x
                                    entry["y"] = entity_y
                                    break
                        if entity_type == 2:
                            for entry in self.npcs[:]: 
                                if entry['id'] == entity_id:
                                    entry["x"] = entity_x
                                    entry["y"] = entity_y
                                    break
                        if entity_type == 9:
                            for entry in self.items[:]: 
                                if entry['id'] == entity_id:
                                    entry["x"] = entity_x
                                    entry["y"] = entity_y
                                    break
                    if splitPacket[0] == ("drop"):
                        new_entity = {"id": int(splitPacket[2]), 
                                      "name": "unknown", 
                                      "owner_id": "unknown", 
                                      "quantity": int(splitPacket[5]), 
                                      "vnum": int(splitPacket[1]), 
                                      "x": int(splitPacket[3]), 
                                      "y": int(splitPacket[4])}
                        self.items.append(new_entity)
                    if splitPacket[0] == ("in"):
                        entity_type = int(splitPacket[1])
                        if entity_type == 1:
                            new_entity = {"champion_level": int(splitPacket[39]), 
                                          "family": splitPacket[3], 
                                          "hp_percent": splitPacket[14], 
                                          "id": int(splitPacket[4]), 
                                          "level": int(splitPacket[33]), 
                                          "mp_percent": int(splitPacket[15]), 
                                          "name": splitPacket[2], 
                                          "x": int(splitPacket[5]), 
                                          "y": int(splitPacket[6])}
                            self.players.append(new_entity)
                        if entity_type == 2:
                            new_entity = {"hp_percent": splitPacket[7], 
                                          "id": int(splitPacket[3]), 
                                          "mp_percent": int(splitPacket[8]), 
                                          "name": "unknown",
                                          "vnum": splitPacket[2], 
                                          "x": int(splitPacket[4]), 
                                          "y": int(splitPacket[5])}
                            self.npcs.append(new_entity)
                        if entity_type == 3:
                            new_entity = {"hp_percent": splitPacket[7], 
                                          "id": int(splitPacket[3]), 
                                          "mp_percent": int(splitPacket[8]), 
                                          "name": "unknown",
                                          "vnum": splitPacket[2], 
                                          "x": int(splitPacket[4]), 
                                          "y": int(splitPacket[5])}
                            self.monsters.append(new_entity)
                    if splitPacket[0] == ("su"):
                        attacker_entity_type = int(splitPacket[1])
                        attacker_entity_id = int(splitPacket[2])
                        defender_entity_type = int(splitPacket[3])
                        defender_entity_id = int(splitPacket[4])

                        if defender_entity_type == 3:
                            for entry in self.monsters[:]: 
                                if entry['id'] == defender_entity_id:
                                    entry["hp_percent"] = int(splitPacket[12])
                                    if entry["hp_percent"] == 0:
                                        self.monsters.remove(entry)
                                    break
                    for i in range(len(self.recv_packet_conditions)):
                        try:
                            if self.recv_packet_conditions[i][2]:
                                t_recv_packet_condition = threading.Thread(target=self.exec_recv_packet_condition, args=[self.recv_packet_conditions[i][1], packet, i, self.recv_packet_conditions[i][0]])
                                t_recv_packet_condition.start()
                        except:
                            pass
                if json_msg["type"] == phoenix.Type.query_player_info.value:
                    player_info = json_msg["player_info"]
                    self.id = player_info["id"]
                    self.name = player_info["name"]
                    self.pos_x = player_info["x"]
                    self.pos_y = player_info["y"]
                    self.map_id = player_info["map_id"]
                    self.level = player_info["level"]
                    self.champion_level = player_info["champion_level"]
                    self.hp_percent = player_info["hp_percent"]
                    self.mp_percent = player_info["mp_percent"]
                    self.is_resting = player_info["is_resting"]
                    self.map_array = loadMap(self.map_id)
                if json_msg["type"] == phoenix.Type.query_inventory.value:
                    inventory = json_msg["inventory"]
                    self.equip = inventory["equip"]
                    self.etc = inventory["etc"]
                    self.gold = inventory["gold"]
                    self.main = inventory["main"]
                if json_msg["type"] == phoenix.Type.query_skills_info.value:
                    self.skills = json_msg["skills"]
                if json_msg["type"] == phoenix.Type.query_map_entities.value:
                    self.items = json_msg["items"]
                    self.monsters = json_msg["monsters"]
                    self.npcs = json_msg["npcs"]
                    self.players = json_msg["players"]
            else:
                time.sleep(0.01)
        print(f"{self.name} lost connection")
        self.api.close()
    
    def walk_to_point(self, point, walk_with_pet = True, skip = 4, timeout = 3):
        player_pos = [self.pos_x, self.pos_y]
        api = self.api
        try:
            Path = findPath(player_pos, point[0], point[1], self.map_array)
            if Path != []:
                lastpath = len(Path)-1
                for i in range(0, len(Path), skip):
                    if self.stop_script:
                        raise SystemExit
                    x = Path[i][0]
                    y = Path[i][1]

                    api.player_walk(x, y)
                    if walk_with_pet:
                        api.pets_walk(x, y)
                    startTimer = time.time()
                    while 1:
                        if self.pos_x == x and self.pos_y == y:
                            break
                        if time.time() - startTimer > timeout:
                            break
                        if self.stop_script:
                            raise SystemExit
                        else:
                            time.sleep(0.1)
                api.player_walk(Path[lastpath][0], Path[lastpath][1])
                if walk_with_pet:
                    api.pets_walk(Path[lastpath][0], Path[lastpath][1])
            else:
                print("Failed to find a path")
        except Exception as e:
            print(f"Error in walk_to_point: {e}")

    def walk_and_switch_map(self, point, walk_with_pet = True, skip = 4, timeout = 3):
        player_pos = [self.pos_x, self.pos_y]
        api = self.api
        try:
            Path = findPath(player_pos, point[0], point[1], self.map_array)
            if Path != []:
                lastpath = len(Path)-1
                for i in range(0, len(Path), skip):
                    if self.stop_script:
                        raise SystemExit
                    x = Path[i][0]
                    y = Path[i][1]

                    api.player_walk(x, y)
                    if walk_with_pet:
                        api.pets_walk(x, y)
                    startTimer = time.time()
                    while 1:
                        if self.pos_x == x and self.pos_y == y:
                            break
                        if time.time() - startTimer > timeout:
                            break
                        if self.stop_script:
                            raise SystemExit
                        else:
                            time.sleep(0.1)
                while self.map_changed == False:
                    random_x = random.choice([-1,1,0])
                    random_y = random.choice([-1,1,0])
                    api.player_walk(Path[lastpath][0]+random_x, Path[lastpath][1]+random_y)
                    if walk_with_pet:
                        api.pets_walk(Path[lastpath][0]+random_x, Path[lastpath][1]+random_y)
                    for i in range(50):
                        time.sleep(0.1)
                        if self.map_changed:
                            break
                print("reached new map")             
            else:
                print("Failed to find a path")
        except Exception as e:
            print(f"Error in walk_and_switch_map: {e}")

    def use_item(self, item_vnum, inventory_type):
        if inventory_type == "equip":
            for item in self.equip:
                if item_vnum == item["vnum"]:
                    item_position = item["position"]
                    self.api.send_packet(f"u_i 1 {self.id} 0 {item_position} 0 0")
                    return True
        if inventory_type == "main":
            for item in self.main:
                if item_vnum == item["vnum"]:
                    item_position = item["position"]
                    self.api.send_packet(f"u_i 1 {self.id} 1 {item_position} 0 0")
                    return True
        if inventory_type == "etc":
            for item in self.etc:
                if item_vnum == item["vnum"]:
                    item_position = item["position"]
                    self.api.send_packet(f"u_i 1 {self.id} 2 {item_position} 0 0")
                    return True

        print(f"Couldnt find item with vnum: {item_vnum} in inventory: {inventory_type}")
        return False

    def put_item_in_trade(self, vnum, amount):
        inv_blocks = {
            0: self.equip,
            1: self.main,
            2: self.etc,
        }

        for inv_type, block in inv_blocks.items():
            for item in block:
                if item.get("vnum") == vnum:
                    slot = item.get("position")
                    qty = item.get("quantity", item.get("amount", item.get("count", 0)))
                    trade_qty = min(amount, qty)
                    if trade_qty > 0:
                        self.api.send_packet(f"exc_list 0 0 {inv_type} {slot} {trade_qty}")
                        return True
        print(f"Item vnum {vnum} not found in inventory")
        return False

    def update_map_change(self):
        self.map_changed = True
        time.sleep(0.5)
        self.map_changed = False

    def find_field(self, a, b, a_angle, b_angle):
        return calculate_field_location([int(a[0]), int(a[1])], [int(b[0]), int(b[1])], float(a_angle), float(b_angle), self.map_array)
        
    def find_point_b(self, x, y, angle, offset = 20):
        return calculate_point_B_position(int(x), int(y), float(angle), self.map_array, offset)

    def randomize_delay(self, min_val, max_val, decimals=1000):
        if min_val <= 0 and max_val <= 0:
            return 0
        if min_val > max_val:
            temp_val = min_val
            min_val = max_val
            max_val = temp_val
        if min_val == max_val:
            return min_val

        min_val = str(min_val)[:5]
        max_val = str(max_val)[:5]

        return random.randint(float(min_val)*decimals, float(max_val)*decimals)/decimals

    def queries(self, delay=1, player_info = True, inventory = True, skills = True, entities = True):
        time.sleep(delay)
        # calling queries
        if player_info:
            self.api.query_player_information()
            time.sleep(delay)
        if inventory:
            self.api.query_inventory()
            time.sleep(delay)
        if skills:
            self.api.query_skills_info()
            time.sleep(delay)
        if entities:
            self.api.query_map_entities()
    
    def exec_recv_packet_condition(self, code, packet, index, cond_name):
        try:
            exec(code)
        except Exception as e:
            try:
                self.recv_packet_conditions.pop(index)
                print(f"\nError executing recv_packet condition: {cond_name}\nError: {e}\nCondition was removed.")
            except:
                pass

    def exec_send_packet_condition(self, code, packet, index, cond_name):
        try:
            exec(code)
        except Exception as e:
            try:
                self.send_packet_conditions.pop(index)
                print(f"\nError executing send_packet condition: {cond_name}\nError: {e}\nCondition was removed.")
            except:
                pass

    def exec_periodic_conditions(self):
        j = 0
        while True:
            try:
                for i in range(len(self.periodical_conditions)):
                    if self.periodical_conditions[i][2] and j % self.periodical_conditions[i][3] == 0:
                        try:
                            exec(self.periodical_conditions[i][1])
                        except Exception as e:
                            try:
                                self.send_packet_conditions.pop(self.send_packet_conditions.index(self.periodical_conditions[i]))
                                print(f"\nError executing periodical condition: {self.periodical_conditions[i][0]}\nError: {e}\nCondition was removed.")
                            except:
                                pass
            except:
                pass
            j+=1
            time.sleep(0.1)
   
    # there was some issue with calling packet.split directly in some rare cases, hence this function
    def split_packet(self, packet, delimeter = " "):
        return packet.split(delimeter)

"""

start = time.time()
parser = Parser()
parser.parseDocument(text)

#print(parser.global_scope["imported_modules"])
print(time.time()-start)


