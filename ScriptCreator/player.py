import time
import json
import phoenix
import threading
import asyncio
import ast
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from queue import Queue
from getports import returnCorrectPort, returnCorrectPID
from path import loadMap, findPath
from calculatefieldlocation import calculate_field_location, calculate_point_B_position
import random
import math
import subprocess
import gfless_api
import textwrap
try:
    import psutil
except ImportError:  # psutil is optional but recommended
    psutil = None
import pywinctl as pwc

from PyQt5 import QtWidgets

# player class which can be reused in other standalone apis
class Player:
    def __init__(self, name=None, on_disconnect=None):
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
        self._cond_counter = 0

        # caches for compiled condition functions
        # maps condition name to a tuple of (source_code, compiled_func)
        self._compiled_recv_conditions = {}
        self._compiled_send_conditions = {}
        self._compiled_periodical_conditions = {}

        # internal state for periodical walking
        # track per-condition cooldowns and thread context
        self._periodic_walking = set()
        self._last_periodic_walk = {}
        self._periodic_ctx = threading.local()
        self._periodic_cond_lock = threading.Lock()

        # walking coordination
        self.walk_lock = threading.Lock()
        self.walk_queue = Queue()
        self._walk_thread = threading.Thread(target=self._process_walk_queue, daemon=True)
        self._walk_thread.start()

        # dedicated executor for heavy path computations
        self._path_executor = ThreadPoolExecutor(max_workers=1)
        
        # asyncio event loop for non-blocking tasks
        self.loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._loop_thread.start()

        # indicates when a script has been loaded into this player
        self.script_loaded = False

        # group info
        self.leadername = ""
        self.leaderID = 0
        self.partyname = []
        self.partyID = []

        # callback when connection is lost
        self.on_disconnect = on_disconnect
        
        # initialize 100 empty attributes so user can use them as he wants
        for i in range(1, 50):
            setattr(self, f'attr{i}', 0)

        for i in range(51, 101):
            setattr(self, f'attr{i}', [])

        if name is not None:
            # initialize api
            self.port = returnCorrectPort(self.name)
            self.PIDnum = returnCorrectPID(self.name)
            self.api = phoenix.Api(self.port)
            self.stop_script = False
            pl_thread = threading.Thread(target=self.packetlogger)
            pl_thread.setDaemon(True)
            pl_thread.start()

            t = threading.Thread(target=self.queries, args=[0.25, ])
            t.start()

            # start periodic conditions loop
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.exec_periodic_conditions())
            )

    def packetlogger(self):
        while self.api.working():
            if not self.api.empty():
                msg = self.api.get_message()
                json_msg = json.loads(msg)
                if json_msg["type"] == phoenix.Type.packet_send.value:
                    packet = json_msg["packet"]
                    splitPacket = packet.split()
                    if splitPacket[0] == "select":
                        gfless_api.close_login_pipe()
                    #print(f"[SEND]: {packet}")
                    if splitPacket[0] == "walk":
                        self.pos_x, self.pos_y = int(splitPacket[1]), int(splitPacket[2])
                    for i, cond in list(enumerate(self.send_packet_conditions)):
                        try:
                            if cond[2]:
                                self.exec_send_packet_condition(
                                    cond[1],
                                    packet,
                                    i,
                                    cond[0],
                                )
                        except Exception as e:
                            print(f"Error scheduling send_packet condition: {e}")
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
                    for i, cond in list(enumerate(self.recv_packet_conditions)):
                        try:
                            if cond[2]:
                                self.exec_recv_packet_condition(
                                    cond[1],
                                    packet,
                                    i,
                                    cond[0],
                                )
                        except Exception as e:
                            print(f"Error scheduling recv_packet condition: {e}")
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
        # purge any queued walk commands to avoid errors after disconnect
        with self.walk_queue.mutex:
            self.walk_queue.queue.clear()
        # attempt to reconnect before giving up
        for delay in (1, 2, 4, 8):
            if self.stop_script:
                break
            try:
                self.api = phoenix.Api(self.port)
                threading.Thread(target=self.packetlogger, daemon=True).start()
                return
            except OSError:
                time.sleep(delay)
        self.stop_script = True
        if callable(self.on_disconnect):
            try:
                self.on_disconnect(self)
            except Exception as e:
                print(f"Error in disconnect callback: {e}")

    def _process_walk_queue(self):
        while True:
            func, args = self.walk_queue.get()
            if not self.api.working() or self.stop_script:
                continue
            try:
                func(*args)
            except OSError as e:
                if getattr(e, "winerror", None) == 10053:
                    continue
                print(f"Error executing walk command: {e}")
            except Exception as e:
                print(f"Error executing walk command: {e}")
    
    async def walk_to_point(self, point, radius=0, walk_with_pet=True, skip=4, timeout=3, proximity=2):
        """Walk the player to ``point`` using non-blocking asyncio primitives.

        ``point`` may be a sequence ``[x, y]`` or an object exposing ``x`` and
        ``y``. ``radius`` adds a random offset to the destination; if the
        resulting point is unreachable, the original coordinates are used as a
        fallback. Parameters ``walk_with_pet``, ``skip`` and ``timeout`` mirror
        the behaviour of the old API. ``skip`` defaults to three nodes (roughly
        four cells between waypoints) and ``timeout`` to three seconds. The
        walk will abort if the map changes during execution. ``proximity``
        defines how close the player must be to a node before it is considered
        reached.
          """

        with self.walk_lock:
            cond = getattr(self._periodic_ctx, "current", None)
            if cond:
                now = time.time()
                last = self._last_periodic_walk.get(cond, 0)
                if cond in self._periodic_walking or now - last < 10:
                    return
                self._periodic_walking.add(cond)

        # Normalise the point into a plain list of coordinates
        if hasattr(point, "x") and hasattr(point, "y"):
            point = [point.x, point.y]
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            point = list(point)
        else:
            raise TypeError("point must be a sequence or expose 'x' and 'y'")

        # Allow ``radius`` to be passed as a string
        if isinstance(radius, str):
            try:
                radius = int(radius)
            except ValueError:
                radius = 0

        target = point[:]  # keep original destination for fallback
        if radius > 0:
            rand_x = random.randint(-radius, radius)
            rand_y = random.randint(-radius, radius)
            point = [point[0] + rand_x, point[1] + rand_y]

        api = self.api
        start_map = self.map_id
        loop = asyncio.get_running_loop()
        try:
            while True:
                player_pos = [self.pos_x, self.pos_y]
                start_time = time.perf_counter()
                Path = await loop.run_in_executor(
                    self._path_executor,
                    findPath,
                    player_pos,
                    [point[0], point[1]],
                    self.map_array,
                    self.map_id,
                )
                elapsed = time.perf_counter() - start_time
                if Path == [] and radius > 0:
                    start_time = time.perf_counter()
                    Path = await loop.run_in_executor(
                        self._path_executor,
                        findPath,
                        player_pos,
                        target,
                        self.map_array,
                        self.map_id,
                    )
                    elapsed = time.perf_counter() - start_time
                    point = target
                if Path == []:
                    print("Failed to find a path")
                    break
                print(f"Path found in {elapsed:.3f} seconds")
                lastpath = len(Path) - 1
                success = True
                for i in range(0, len(Path), skip):
                    if self.stop_script or self.map_id != start_map:
                        return
                    node = Path[i]
                    if hasattr(node, "x") and hasattr(node, "y"):
                        x, y = node.x, node.y
                    else:
                        x, y = node[0], node[1]

                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (x, y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (x, y)))
                    startTimer = time.time()
                    deadline = startTimer + timeout * 2
                    last_send = startTimer
                    while True:
                        if self.map_id != start_map:
                            return
                        if math.hypot(self.pos_x - x, self.pos_y - y) <= proximity:
                            break
                        now = time.time()
                        if now >= deadline:
                            success = False
                            break
                        if self.stop_script:
                            raise SystemExit
                        if now - last_send >= timeout:
                            with self.walk_lock:
                                self.walk_queue.put((api.player_walk, (x, y)))
                                if walk_with_pet:
                                    self.walk_queue.put((api.pets_walk, (x, y)))
                            last_send = now
                        await asyncio.sleep(0.02)
                    if not success:
                        break
                if success:
                    last_node = Path[lastpath]
                    if hasattr(last_node, "x") and hasattr(last_node, "y"):
                        last_x, last_y = last_node.x, last_node.y
                    else:
                        last_x, last_y = last_node[0], last_node[1]
                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (last_x, last_y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (last_x, last_y)))
                    break
                else:
                    await asyncio.sleep(timeout)
                    continue
        except Exception as e:
            print(f"Error in walk_to_point: {e}")
        finally:
            if cond:
                with self.walk_lock:
                    self._periodic_walking.discard(cond)
                    self._last_periodic_walk[cond] = time.time()


    async def walk_and_switch_map(self, point, walk_with_pet=True, skip=3, timeout=3):
        """Walk to ``point`` and wait for a map change using asyncio."""

        # Normalise ``point`` just like in ``walk_to_point``
        if hasattr(point, "x") and hasattr(point, "y"):
            point = [point.x, point.y]
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            point = list(point)
        else:
            raise TypeError("point must be a sequence or expose 'x' and 'y'")

        player_pos = [self.pos_x, self.pos_y]
        api = self.api
        loop = asyncio.get_running_loop()
        try:
            Path = await loop.run_in_executor(
                self._path_executor,
                findPath,
                player_pos,
                [point[0], point[1]],
                self.map_array,
                self.map_id,
            )
            if Path:
                lastpath = len(Path) - 1
                for i in range(skip, len(Path), skip):
                    if self.stop_script:
                        raise SystemExit
                    node = Path[i]
                    if hasattr(node, "x") and hasattr(node, "y"):
                        x, y = node.x, node.y
                    else:
                        x, y = node[0], node[1]

                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (x, y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (x, y)))
                    startTimer = time.time()
                    while True:
                        if abs(self.pos_x - x) <= 1 and abs(self.pos_y - y) <= 1:
                            break
                        if time.time() - startTimer > timeout:
                            break
                        if self.stop_script:
                            raise SystemExit
                        with self.walk_lock:
                            self.walk_queue.put((api.player_walk, (x, y)))
                            if walk_with_pet:
                                self.walk_queue.put((api.pets_walk, (x, y)))
                        await asyncio.sleep(timeout)
                start = time.time()
                while not self.map_changed and time.time() - start < 10:
                    random_x = random.choice([-1, 1, 0])
                    random_y = random.choice([-1, 1, 0])
                    last_node = Path[lastpath]
                    if hasattr(last_node, "x") and hasattr(last_node, "y"):
                        base_x, base_y = last_node.x, last_node.y
                    else:
                        base_x, base_y = last_node[0], last_node[1]

                    with self.walk_lock:
                        self.walk_queue.put((api.player_walk, (base_x + random_x, base_y + random_y)))
                        if walk_with_pet:
                            self.walk_queue.put((api.pets_walk, (base_x + random_x, base_y + random_y)))
                    for _ in range(50):
                        await asyncio.sleep(0.1)
                        if self.map_changed:
                            break
                if not self.map_changed:
                    print("timeout waiting for map change")
                else:
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

    def put_items_in_trade(self, items):
        inv_blocks = {
            0: self.equip,
            1: self.main,
            2: self.etc,
        }

        packet_parts = ["exc_list", "0", "0"]
        for inv_type, vnum, amount in items:
            block = inv_blocks.get(inv_type, [])
            best_slot = None
            best_qty = 0
            for item in block:
                if item.get("vnum") == vnum:
                    slot = item.get("position")
                    qty = item.get("quantity", item.get("amount", item.get("count", 0)))
                    if qty >= amount:
                        best_slot = slot
                        best_qty = amount
                        break
                    elif qty > best_qty:
                        best_slot = slot
                        best_qty = qty
            if best_slot is None or best_qty == 0:
                print("Insufficient items to exchange")
                return False
            packet_parts.extend([str(inv_type), str(best_slot), str(best_qty)])

        if len(packet_parts) > 3:
            self.api.send_packet(" ".join(packet_parts))
            return True
        print("Insufficient items to exchange")
        return False

    def put_item_in_trade(self, items):
        return self.put_items_in_trade(items)

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

        min_i = int(min_val * decimals)
        max_i = int(max_val * decimals)

        return random.randint(min_i, max_i) / decimals

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
            cached = self._compiled_recv_conditions.get(cond_name)
            if not cached or cached[0] != code:
                func = self._compile_condition(code, with_packet=True)
                self._compiled_recv_conditions[cond_name] = (code, func)
            else:
                func = cached[1]
            asyncio.run_coroutine_threadsafe(
                self._run_packet_condition(
                    cond_name, func, packet, self.recv_packet_conditions, "recv_packet"
                ),
                self.loop,
            )
        except Exception as e:
            try:
                self.recv_packet_conditions.pop(index)
                self._compiled_recv_conditions.pop(cond_name, None)
                print(
                    f"\nError executing recv_packet condition: {cond_name}\nError: {e}\nCondition was removed."
                )
            except Exception as e2:
                print(f"Error removing faulty recv_packet condition: {e2}")

    def exec_send_packet_condition(self, code, packet, index, cond_name):
        try:
            cached = self._compiled_send_conditions.get(cond_name)
            if not cached or cached[0] != code:
                func = self._compile_condition(code, with_packet=True)
                self._compiled_send_conditions[cond_name] = (code, func)
            else:
                func = cached[1]
            asyncio.run_coroutine_threadsafe(
                self._run_packet_condition(
                    cond_name, func, packet, self.send_packet_conditions, "send_packet"
                ),
                self.loop,
            )
        except Exception as e:
            try:
                self.send_packet_conditions.pop(index)
                self._compiled_send_conditions.pop(cond_name, None)
                print(
                    f"\nError executing send_packet condition: {cond_name}\nError: {e}\nCondition was removed."
                )
            except Exception as e2:
                print(f"Error removing faulty send_packet condition: {e2}")

    async def exec_periodic_conditions(self):
        j = 0
        running = {}
        while True:
            try:
                with self._periodic_cond_lock:
                    conds = list(self.periodical_conditions)
                for idx, (name, code, active, interval) in enumerate(conds):
                    if not active or j % interval != 0:
                        continue
                    cached = self._compiled_periodical_conditions.get(name)
                    if not cached or cached[0] != code:
                        func = self._compile_condition(code)
                        self._compiled_periodical_conditions[name] = (code, func)
                    else:
                        func = cached[1]
                    if name in running and not running[name].done():
                        continue
                    task = asyncio.create_task(self._run_periodic_condition(name, func))
                    running[name] = task
            except Exception as e:
                print(f"Error executing periodic conditions loop: {e}")
            j += 1
            await asyncio.sleep(0.1)

    def _compile_condition(self, script, with_packet=False):
        """Compile a condition script into an async callable, replacing time.sleep with await asyncio.sleep."""
        func_name = f"_cond_func_{self._cond_counter}"
        self._cond_counter += 1

        tree = ast.parse(script, mode="exec")

        class AwaitTransformer(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                ):
                    # Replace time.sleep with await asyncio.sleep
                    if node.func.value.id == "time" and node.func.attr == "sleep":
                        new_call = ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="asyncio", ctx=ast.Load()),
                                attr="sleep",
                                ctx=ast.Load(),
                            ),
                            args=node.args,
                            keywords=node.keywords,
                        )
                        return ast.Await(value=new_call)
                    # Ensure asynchronous Player methods are awaited
                    if node.func.value.id == "self" and node.func.attr in {
                        "walk_to_point",
                        "walk_and_switch_map",
                    }:
                        return ast.Await(value=node)
                return node

        tree = AwaitTransformer().visit(tree)
        ast.fix_missing_locations(tree)

        args = [ast.arg(arg="self")]
        if with_packet:
            args.append(ast.arg(arg="packet"))

        func_def = ast.AsyncFunctionDef(
            name=func_name,
            args=ast.arguments(
                posonlyargs=[],
                args=args,
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=tree.body,
            decorator_list=[],
        )

        module = ast.Module(body=[func_def], type_ignores=[])
        ast.fix_missing_locations(func_def)
        ast.fix_missing_locations(module)
        globs = {"asyncio": asyncio, "time": time}
        exec(compile(module, func_name, "exec"), globs)
        return globs[func_name]

    async def _run_packet_condition(self, name, func, packet, store_list, cond_type):
        try:
            await func(self, packet)
        except Exception as e:
            try:
                for idx, cond in enumerate(store_list):
                    if cond[0] == name:
                        store_list.pop(idx)
                        break
                print(
                    f"\nError executing {cond_type} condition: {name}\nError: {e}\nCondition was removed."
                )
            except Exception as e2:
                print(f"Error removing faulty {cond_type} condition: {e2}")

    async def _run_periodic_condition(self, name, func):
        self._periodic_ctx.current = name
        try:
            await func(self)
        except Exception as e:
            try:
                with self._periodic_cond_lock:
                    for idx, cond in enumerate(self.periodical_conditions):
                        if cond[0] == name:
                            self.periodical_conditions.pop(idx)
                            break
                self._compiled_periodical_conditions.pop(name, None)
                print(
                    f"\nError executing periodical condition: {name}\nError: {e}\nCondition was removed."
                )
            except Exception:
                print(
                    f"\nError executing periodical condition: {name}\nError: {e}\nCondition was removed."
                )
        finally:
            self._periodic_ctx.current = None
   
    # there was some issue with calling packet.split directly in some rare cases, hence this function
    def split_packet(self, packet, delimeter = " "):
        return packet.split(delimeter)

    def reset_attrs(self):
        """Reset attr1 through attr99 to 0 and clear leader info."""
        for i in range(1, 100):
            setattr(self, f'attr{i}', 0)
        self.leadername = ""
        self.leaderID = 0

    def invite_members(self):
        """Invite all stored group members with a 3-second delay between invites."""
        if not isinstance(self.attr51, list):
            return
        for name in self.attr51:
            try:
                self.api.send_packet(f"$Invite {name}")
                time.sleep(3)
            except Exception as e:
                print(f"Failed to invite {name}: {e}")

    def close_game(self):
        """Terminate the Nostale client associated with this player."""
        pid = None
        if psutil is not None:
            try:
                for conn in psutil.net_connections(kind="tcp"):
                    if conn.laddr and conn.laddr.port == self.port and conn.pid:
                        pid = conn.pid
                        break
            except Exception:
                pass

        if pid is None:
            try:
                wins = pwc.getWindowsWithTitle("Nostale")
                if wins:
                    pid = wins[0].getPid()
            except Exception:
                pass

        win = None
        if pid:
            try:
                subprocess.check_call(["taskkill", "/PID", str(pid), "/F"])
                return True
            except subprocess.CalledProcessError:
                pass

            try:
                subprocess.check_call([
                    "wmic",
                    "process",
                    "where",
                    f"processid={pid}",
                    "call",
                    "terminate",
                ])
                return True
            except Exception:
                pass

            try:
                wins = pwc.getWindowsWithTitle("Nostale")
                if wins:
                    win = wins[0]
            except Exception:
                pass

            if win:
                try:
                    win.close()
                    return True
                except Exception:
                    pass
        return False

