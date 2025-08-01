import time
import json
import phoenix
import threading
from typing import Optional
from getports import returnCorrectPort
from path import loadMap, findPath
from calculatefieldlocation import calculate_field_location, calculate_point_B_position
import random

from PyQt5 import QtWidgets
import gfless_api

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

        # indicates when a script has been loaded into this player
        self.script_loaded = False
        
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
            Path = findPath(player_pos, [point[0], point[1]], self.map_array)
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
                    self.api.send_packet(f"wear {item_position} 0")
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

    def auto_login(self, lang: int, server: int, channel: int, character: int, *, pid: Optional[int] = None, exe_name: str = "NostaleClientX.exe"):
        """Reconnect using gfless_api login sequence."""
        gfless_api.login(lang, server, channel, character, pid=pid, exe_name=exe_name)

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
                                print(f"\nError executing periodical condition: {self.periodical_conditions[i][0]}\nError: {e}\nCondition was removed.")
            except:
                pass
            j+=1
            time.sleep(0.1)
   
    # there was some issue with calling packet.split directly in some rare cases, hence this function
    def split_packet(self, packet, delimeter = " "):
        return packet.split(delimeter)



test = 10

