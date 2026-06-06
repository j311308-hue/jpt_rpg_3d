import pygame
import math
import sys
import traceback
import json
import os
import random
import copy
from enum import Enum

# ==========================================
#                 SETTINGS
# ==========================================
MAP_SIZE = 48
TILE_SIZE = 64
WIDTH = 1024
HEIGHT = 768
FPS = 60
FOV = math.pi / 3
NUM_RAYS = 150
DELTA_ANGLE = FOV / NUM_RAYS
MAX_DEPTH = 800
PLAYER_SPEED = 3.5
PLAYER_ROTATION_SPEED = 0.05
WALL_HEIGHT_MULTIPLIER = 21000

class TileType(Enum):
    EMPTY = 0; WALL_BRICK = 1; WALL_STONE = 2; WALL_WOOD = 3
    DOOR = 4; DOOR_SILVER = 5; DOOR_GOLD = 6
    TREE = 10; DEAD_TREE = 11; BUSH = 12; ROCK = 13
    STANDING_TORCH = 14; WALL_TORCH = 15
    ITEM_DAGGER = 20; ITEM_KEY = 21; ITEM_KEY_SILVER = 22; ITEM_KEY_GOLD = 23
    ITEM_KEY_DUNGEON = 24; ITEM_HEALTH_POTION = 25; ITEM_FOOD = 26; ITEM_ARTIFACT = 27
    PLAYER_SPAWN = 50; ENEMY_GHOST = 60

MAP_DATA_FILE = "map_data.json"
BOSS_DATA_FILE = "boss_data.json"

# ==========================================
#         RESOURCE & AUDIO LOADER
# ==========================================
pygame.init()
try:
    pygame.mixer.init()
    MIXER_READY = True
except Exception:
    MIXER_READY = False

def load_image_safe(filename, alpha=False):
    try:
        if os.path.exists(filename):
            img = pygame.image.load(filename)
            return img.convert_alpha() if alpha else img.convert()
    except: pass
    return None

# Load provided assets dynamically
TEX_BRICK = load_image_safe("Brick_Wall_64x64.png")
SPRITE_BUSH = load_image_safe("bush.png", alpha=True)
SPRITE_BUSH2 = load_image_safe("bush_2.png", alpha=True)
SPRITE_BOSS_IDLE = load_image_safe("boss_idle.png", alpha=True)
SPRITE_BOSS_ATTACK = load_image_safe("boss_attack.png", alpha=True)
SPRITE_FIREBALL = load_image_safe("fireball.png", alpha=True)
ICON_ARTIFACT = load_image_safe("artifact.png", alpha=True)
BG_MENU = load_image_safe("1780692702140.png")

def play_music(music_type="bgm"):
    if not MIXER_READY: return
    pygame.mixer.music.stop()
    
    track = None
    if music_type == "bgm":
        if os.path.exists("bgm.ogg"): track = "bgm.ogg"
        elif os.path.exists("bgm.mp3"): track = "bgm.mp3"
    elif music_type == "boss":
        if os.path.exists("boss_fight.mp3"): track = "boss_fight.mp3"
        
    if track:
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(-1)
        except: pass

# Import new systems
try:
    from asset_manager import get_asset_manager
    from combat_system import CombatSystem, Enemy
    from stat_system import StatAllocator
except ImportError as e:
    print(f"Warning: Could not import new systems: {e}")

# ==========================================
#               UI & INVENTORY
# ==========================================
class ActionBar:
    def __init__(self, icons_dict):
        self.icons = icons_dict
        self.slot_size = 50
        self.spacing = 10
        self.slots = [
            {"key": pygame.K_1, "label": "1", "name": "Empty", "icon": None, "cd": 0, "max_cd": 30, "type": "none", "cost": 0},
            {"key": pygame.K_2, "label": "2", "name": "Fireball", "icon": None, "cd": 0, "max_cd": 60, "type": "magic", "cost": 10},
            {"key": pygame.K_3, "label": "3", "name": "Heal", "icon": None, "cd": 0, "max_cd": 120, "type": "magic", "cost": 20},
            {"key": pygame.K_4, "label": "4", "name": "Empty", "icon": None, "cd": 0, "max_cd": 10, "type": "none", "cost": 0},
            {"key": pygame.K_5, "label": "5", "name": "Empty", "icon": None, "cd": 0, "max_cd": 10, "type": "none", "cost": 0},
            {"key": pygame.K_6, "label": "6", "name": "Empty", "icon": None, "cd": 0, "max_cd": 10, "type": "none", "cost": 0}
        ]

    def update(self):
        for slot in self.slots:
            if slot["cd"] > 0: slot["cd"] -= 1

    def draw(self, screen):
        total_width = (len(self.slots) * self.slot_size) + ((len(self.slots) - 1) * self.spacing)
        start_x = (WIDTH // 2) - (total_width // 2)
        start_y = HEIGHT - self.slot_size - 20 
        font = pygame.font.SysFont("georgia", 14, bold=True)

        for i, slot in enumerate(self.slots):
            x = start_x + (i * (self.slot_size + self.spacing))
            rect = pygame.Rect(x, start_y, self.slot_size, self.slot_size)
            
            pygame.draw.rect(screen, (40, 30, 20), rect)
            pygame.draw.rect(screen, (150, 150, 150), rect, 2)
            
            if slot["icon"]:
                icon_scaled = pygame.transform.scale(slot["icon"], (self.slot_size - 4, self.slot_size - 4))
                screen.blit(icon_scaled, (x + 2, start_y + 2))
            
            if slot["cd"] > 0:
                cd_ratio = slot["cd"] / slot["max_cd"]
                s = pygame.Surface((self.slot_size, self.slot_size * cd_ratio), pygame.SRCALPHA)
                s.fill((0, 0, 0, 180))
                screen.blit(s, (x, start_y + (self.slot_size * (1 - cd_ratio))))
                
            label = font.render(slot["label"], True, (255, 255, 255))
            screen.blit(label, (x + 5, start_y + 5))

class Inventory:
    def __init__(self, icons_dict):
        self.slots = [None] * 16 
        self.visible = False
        self.rect = pygame.Rect(0, 0, 340, 340) 
        self.icons = icons_dict
        self.cols, self.rows = 4, 4
        self.slot_size, self.margin = 60, 15
        
    def toggle(self):
        self.visible = not self.visible
            
    def add_item(self, name, qty, item_type, desc):
        for slot in self.slots:
            if slot and slot["name"] == name and slot["type"] not in ["weapon", "artifact"]:
                slot["qty"] += qty
                return True
        for i in range(len(self.slots)):
            if self.slots[i] is None:
                self.slots[i] = {"name": name, "qty": qty, "type": item_type, "desc": desc}
                return True
        return False

    def draw(self, screen):
        if not self.visible: return
        sw, sh = screen.get_size()
        self.rect.center = (sw//2, sh//2 - 40)
        
        s = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        s.fill((30, 30, 35, 230))
        screen.blit(s, (self.rect.x, self.rect.y))
        pygame.draw.rect(screen, (200, 180, 100), self.rect, 3)
        font = pygame.font.SysFont("georgia", 12, bold=True)
        
        for i in range(16):
            row, col = i // self.cols, i % self.cols
            sx = self.rect.x + 25 + col * (self.slot_size + self.margin)
            sy = self.rect.y + 50 + row * (self.slot_size + self.margin)
            s_rect = pygame.Rect(sx, sy, self.slot_size, self.slot_size)
            pygame.draw.rect(screen, (60, 60, 65), s_rect)
            pygame.draw.rect(screen, (100, 100, 110), s_rect, 2)
            
            slot = self.slots[i]
            if slot:
                icon = self.icons.get(slot["name"].lower(), None)
                if icon:
                    screen.blit(pygame.transform.scale(icon, (self.slot_size-4, self.slot_size-4)), (sx+2, sy+2))
                else:
                    pygame.draw.rect(screen, (150, 50, 150), (sx+5, sy+5, self.slot_size-10, self.slot_size-10))
                
                if slot["qty"] > 1:
                    q_text = font.render(str(slot["qty"]), True, (255, 255, 255))
                    screen.blit(q_text, (sx + self.slot_size - q_text.get_width() - 2, sy + self.slot_size - q_text.get_height() - 2))

# ==========================================
#              BOSS DESIGNER
# ==========================================
class BossDesigner:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("RPGW3D - Elite Boss Designer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("georgia", 20, bold=True)
        self.font_small = pygame.font.SysFont("georgia", 16)
        
        self.boss_data = {
            "name": "Dark Overlord", "hp": 500, "damage": 50,
            "speed": 2.5, "scale": 1.5, "texture": "boss_idle.png"
        }
        
        self.buttons = []
        self.setup_ui()
        self.message = ""
        self.message_timer = 0
        
    def setup_ui(self):
        y_pos, keys, steps = [120, 180, 240, 300], ["hp", "damage", "speed", "scale"], [50, 5, 0.5, 0.2]
        for i, key in enumerate(keys):
            self.buttons.append({"action": f"{key}_minus", "rect": pygame.Rect(400, y_pos[i], 40, 40), "label": "-"})
            self.buttons.append({"action": f"{key}_plus", "rect": pygame.Rect(600, y_pos[i], 40, 40), "label": "+"})

        self.buttons.append({"action": "save", "rect": pygame.Rect(WIDTH//2 - 200, 400, 120, 50), "label": "Save Boss"})
        self.buttons.append({"action": "exit", "rect": pygame.Rect(WIDTH//2 - 200, 470, 120, 50), "label": "Exit"})

    def handle_click(self, pos):
        for btn in self.buttons:
            if btn["rect"].collidepoint(pos):
                act = btn["action"]
                if act == "hp_minus": self.boss_data["hp"] = max(100, self.boss_data["hp"] - 50)
                elif act == "hp_plus": self.boss_data["hp"] += 50
                elif act == "damage_minus": self.boss_data["damage"] = max(5, self.boss_data["damage"] - 5)
                elif act == "damage_plus": self.boss_data["damage"] += 5
                elif act == "speed_minus": self.boss_data["speed"] = max(0.5, round(self.boss_data["speed"] - 0.5, 1))
                elif act == "speed_plus": self.boss_data["speed"] = round(self.boss_data["speed"] + 0.5, 1)
                elif act == "scale_minus": self.boss_data["scale"] = max(0.5, round(self.boss_data["scale"] - 0.2, 1))
                elif act == "scale_plus": self.boss_data["scale"] = round(self.boss_data["scale"] + 0.2, 1)
                elif act == "save":
                    with open(BOSS_DATA_FILE, "w") as f: json.dump(self.boss_data, f)
                    self.message = "Boss Saved!"
                    self.message_timer = 120
                elif act == "exit":
                    play_music("bgm")
                    return True
        return False

    def draw(self):
        self.screen.fill((20, 20, 25))
        title = self.font.render("Boss Designer Studio", True, (255, 200, 100))
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 40))
        
        y_pos, keys = [120, 180, 240, 300], ["hp", "damage", "speed", "scale"]
        labels = ["Health Points", "Attack Damage", "Movement Speed", "Size Scale"]
        
        for i, key in enumerate(keys):
            lbl = self.font_small.render(labels[i], True, (200, 200, 200))
            self.screen.blit(lbl, (200, y_pos[i] + 10))
            val = self.font.render(str(self.boss_data[key]), True, (255, 255, 255))
            self.screen.blit(val, (520 - val.get_width()//2, y_pos[i] + 10))

        mouse_pos = pygame.mouse.get_pos()
        for btn in self.buttons:
            hover = btn["rect"].collidepoint(mouse_pos)
            bg_color = (50, 150, 50) if hover and btn["action"] == "save" else (150, 50, 50) if hover and btn["action"] == "exit" else (60, 60, 70) if not hover else (100, 100, 120)
            if btn["action"] not in ["save", "exit"] and not hover: bg_color = (60, 60, 70)
            elif btn["action"] not in ["save", "exit"]: bg_color = (100, 100, 120)
            elif btn["action"] == "save" and not hover: bg_color = (30, 100, 30)
            elif btn["action"] == "exit" and not hover: bg_color = (100, 30, 30)
                
            pygame.draw.rect(self.screen, bg_color, btn["rect"])
            pygame.draw.rect(self.screen, (200, 200, 200), btn["rect"], 1)
            txt_surf = self.font.render(btn["label"], True, (255, 255, 255))
            self.screen.blit(txt_surf, (btn["rect"].centerx - txt_surf.get_width()//2, btn["rect"].centery - txt_surf.get_height()//2))

        preview_rect = pygame.Rect(WIDTH - 380, 120, 300, 300)
        pygame.draw.rect(self.screen, (30, 30, 40), preview_rect)
        pygame.draw.rect(self.screen, (100, 100, 150), preview_rect, 2)
        
        active_sprite = SPRITE_BOSS_ATTACK if pygame.time.get_ticks() % 1000 > 500 and SPRITE_BOSS_ATTACK else SPRITE_BOSS_IDLE
        if active_sprite:
            scale = self.boss_data["scale"]
            sw, sh = active_sprite.get_size()
            scaled_img = pygame.transform.scale(active_sprite, (int(sw * scale), int(sh * scale)))
            cx, cy = preview_rect.centerx, preview_rect.centery
            self.screen.blit(scaled_img, (cx - scaled_img.get_width()//2, cy - scaled_img.get_height()//2))
        else:
            txt = self.font_small.render("No Sprite Found", True, (150, 150, 150))
            self.screen.blit(txt, (preview_rect.centerx - txt.get_width()//2, preview_rect.centery))

        if self.message_timer > 0:
            self.message_timer -= 1
            msg_surf = self.font.render(self.message, True, (100, 255, 100))
            self.screen.blit(msg_surf, (WIDTH//2 - msg_surf.get_width()//2, HEIGHT - 40))

        pygame.display.flip()

    def run(self):
        play_music("boss")
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: return
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE: 
                    play_music("bgm")
                    return
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if self.handle_click(e.pos): return
            self.draw()
            self.clock.tick(FPS)

# ==========================================
#               MAP EDITOR
# ==========================================
class MapEditor:
    def __init__(self):
        self.base_cell_size, self.editor_width, self.editor_height, self.left_panel_w, self.right_panel_w = 24, 1200, 800, 200, 260
        self.screen = pygame.display.set_mode((self.editor_width, self.editor_height))
        pygame.display.set_caption("RPGW3D Map Editor")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("georgia", 12)
        self.font_large = pygame.font.SysFont("georgia", 16, bold=True)
        self.font_msg = pygame.font.SysFont("georgia", 14, bold=True)
        self.map = [[TileType.EMPTY.value for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        self.active_tile, self.camera_x, self.camera_y, self.zoom = TileType.WALL_BRICK.value, self.left_panel_w + 50, 50, 1.0
        self.save_message = ""
        self.save_message_timer = 0
        self.load_map()

    def load_map(self):
        if os.path.exists(MAP_DATA_FILE):
            try:
                with open(MAP_DATA_FILE, "r") as f:
                    data = json.load(f)
                    if "map" in data:
                        map_data = data["map"]
                        # Validate dimensions
                        if len(map_data) == MAP_SIZE and all(len(row) == MAP_SIZE for row in map_data):
                            self.map = map_data
                            print(f"✓ Map loaded successfully from {MAP_DATA_FILE}")
                        else:
                            print(f"✗ Map size mismatch! Expected {MAP_SIZE}x{MAP_SIZE}, got {len(map_data)}x{len(map_data[0]) if map_data else 0}")
            except Exception as e:
                print(f"✗ Failed to load map: {e}")

    def run(self):
        mouse_down, is_panning, p_start_m, p_start_c = False, False, (0,0), (0,0)
        while True:
            pos = pygame.mouse.get_pos()
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE): 
                    return
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                    try:
                        with open(MAP_DATA_FILE, "w") as f: 
                            json.dump({"map": self.map, "size": MAP_SIZE}, f, indent=2)
                        print(f"✓ Map saved successfully to {MAP_DATA_FILE}")
                        self.save_message = "Map Saved!"
                        self.save_message_timer = 120
                    except Exception as e:
                        print(f"✗ Failed to save map: {e}")
                        self.save_message = "Save Failed!"
                        self.save_message_timer = 120
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if e.button == 1: 
                        mouse_down = True
                        if pos[0] >= self.editor_width - self.right_panel_w:
                            idx = (pos[1] - 40) // 20
                            if 0 <= idx < len(TileType): self.active_tile = list(TileType)[idx].value
                    elif e.button in (2, 3): is_panning, p_start_m, p_start_c = True, pos, (self.camera_x, self.camera_y)
                    elif e.button == 4: self.zoom = min(3.0, self.zoom + 0.1)
                    elif e.button == 5: self.zoom = max(0.5, self.zoom - 0.1)
                elif e.type == pygame.MOUSEBUTTONUP:
                    if e.button == 1: mouse_down = False
                    elif e.button in (2, 3): is_panning = False
                elif e.type == pygame.MOUSEMOTION:
                    if is_panning: self.camera_x, self.camera_y = p_start_c[0] + pos[0] - p_start_m[0], p_start_c[1] + pos[1] - p_start_m[1]
                    elif mouse_down and pos[0] >= self.left_panel_w and pos[0] <= self.editor_width - self.right_panel_w and pos[1] <= self.editor_height - 35:
                        gx, gy = int((pos[0] - self.camera_x) // (24 * self.zoom)), int((pos[1] - self.camera_y) // (24 * self.zoom))
                        if 0 <= gx < MAP_SIZE and 0 <= gy < MAP_SIZE: self.map[gy][gx] = self.active_tile
            
            self.screen.fill((30, 30, 30))
            cell = int(24 * self.zoom)
            for y in range(MAP_SIZE):
                for x in range(MAP_SIZE):
                    px, py = self.camera_x + x * cell, self.camera_y + y * cell
                    if px < self.left_panel_w or px > self.editor_width - self.right_panel_w or py > self.editor_height - 35: continue
                    val = self.map[y][x]
                    rect = pygame.Rect(px, py, cell, cell)
                    if val == 0: pygame.draw.rect(self.screen, (50, 50, 50), rect, 1)
                    else:
                        color = (150, 100, 100) if val in [1,2,3] else (0, 255, 0) if val == 50 else (255, 0, 0) if val == 60 else (139, 69, 19)
                        pygame.draw.rect(self.screen, color, rect)
            
            pygame.draw.rect(self.screen, (40, 40, 40), (0, 0, self.left_panel_w, self.editor_height))
            pygame.draw.rect(self.screen, (40, 40, 40), (self.editor_width - self.right_panel_w, 0, self.right_panel_w, self.editor_height))
            self.screen.blit(self.font_large.render("Tiles", True, (255, 255, 255)), (self.editor_width - self.right_panel_w + 10, 10))
            y_off = 40
            for item in TileType:
                c = (255, 255, 0) if self.active_tile == item.value else (200, 200, 200)
                self.screen.blit(self.font.render(f"{item.name} ({item.value})", True, c), (self.editor_width - self.right_panel_w + 10, y_off))
                y_off += 20
            
            # Draw save message
            if self.save_message_timer > 0:
                self.save_message_timer -= 1
                msg_color = (100, 255, 100) if "Saved" in self.save_message else (255, 100, 100)
                msg_surf = self.font_msg.render(self.save_message, True, msg_color)
                self.screen.blit(msg_surf, (self.editor_width // 2 - msg_surf.get_width() // 2, self.editor_height - 40))
            
            # Draw instructions
            instr_surf = self.font.render("Press S to Save | ESC to Exit", True, (150, 150, 150))
            self.screen.blit(instr_surf, (10, self.editor_height - 25))
            
            pygame.display.flip()
            self.clock.tick(FPS)

# ==========================================
#               GAME ENGINE
# ==========================================
class Game:
    def __init__(self, stats=None):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("RPGW3D - Engine")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("georgia", 18, bold=True)
        self.font_small = pygame.font.SysFont("georgia", 14)
        
        # Initialize combat system with custom or default stats
        if stats:
            self.combat = CombatSystem(stats["strength"], stats["intelligence"], stats["endurance"])
        else:
            self.combat = CombatSystem()
        
        # Load Inventory Assets
        icons = {"ancient artifact": ICON_ARTIFACT}
        self.inventory = Inventory(icons)
        self.inventory.add_item("Ancient Artifact", 1, "artifact", "A glowing relict of power")
        self.action_bar = ActionBar(icons)
        
        self.health = self.combat.max_health
        self.max_health = self.combat.max_health
        self.mana = self.combat.max_mana
        self.max_mana = self.combat.max_mana
        
        self.px, self.py, self.p_angle = 2.5, 2.5, 0.0
        self.show_stat_screen = False
        
        # Enemy management
        self.enemies = []
        
        # Load Map & Sprites
        self.sprites = []
        self.map = self.load_map_safe()
        
        # Z-Buffer for Sprite Rendering
        self.z_buffer = [0.0] * NUM_RAYS

    def load_map_safe(self):
        default_map = [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        for i in range(MAP_SIZE): default_map[0][i] = default_map[MAP_SIZE-1][i] = default_map[i][0] = default_map[i][MAP_SIZE-1] = 1
            
        try:
            if os.path.exists(MAP_DATA_FILE):
                with open(MAP_DATA_FILE, "r") as f:
                    data = json.load(f)
                    if "map" in data:
                        map_data = data["map"]
                        # Validate dimensions BEFORE using
                        if len(map_data) == MAP_SIZE and all(len(row) == MAP_SIZE for row in map_data):
                            default_map = map_data
                            print(f"✓ Map loaded successfully from {MAP_DATA_FILE}")
                        else:
                            print(f"✗ Map data size mismatch! Expected {MAP_SIZE}x{MAP_SIZE}, got {len(map_data)}x{len(map_data[0]) if map_data else 0}. Using default map.")
        except Exception as e:
            print(f"✗ Failed to load map: {e}. Using default map.")
        
        # Extract Spawn & Sprites from map
        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                val = default_map[y][x]
                if val == TileType.PLAYER_SPAWN.value:
                    self.px, self.py = x + 0.5, y + 0.5
                    default_map[y][x] = 0
                elif val == TileType.BUSH.value:
                    self.sprites.append({"type": "bush", "x": x + 0.5, "y": y + 0.5, "var": random.randint(1,2)})
                    default_map[y][x] = 0
                elif val == TileType.ENEMY_GHOST.value:
                    self.enemies.append(Enemy(x + 0.5, y + 0.5, "ghost"))
                    default_map[y][x] = 0
        return default_map

    def draw_raycast(self):
        pygame.draw.rect(self.screen, (30, 30, 40), (0, 0, WIDTH, HEIGHT//2))
        pygame.draw.rect(self.screen, (40, 50, 40), (0, HEIGHT//2, WIDTH, HEIGHT//2))
        
        tex_width = TEX_BRICK.get_width() if TEX_BRICK else 64
        
        for ray in range(NUM_RAYS):
            ray_angle = self.p_angle - FOV/2 + ray * DELTA_ANGLE
            sin_a, cos_a = math.sin(ray_angle), math.cos(ray_angle)
            
            dist, step, hit_wall, wall_type = 0.0, 0.05, False, 0
            cx, cy = self.px, self.py
            
            while not hit_wall and dist < MAX_DEPTH:
                dist += step
                cx = self.px + cos_a * dist
                cy = self.py + sin_a * dist
                ix, iy = int(cx), int(cy)
                
                if 0 <= ix < MAP_SIZE and 0 <= iy < MAP_SIZE:
                    if 0 < self.map[iy][ix] < 10:
                        hit_wall, wall_type = True, self.map[iy][ix]
                else: hit_wall = True
                    
            if hit_wall:
                dist *= math.cos(self.p_angle - ray_angle)
                dist = max(0.1, dist)
                self.z_buffer[ray] = dist
                
                wall_h = min(HEIGHT * 2, WALL_HEIGHT_MULTIPLIER / dist)
                
                ray_w = WIDTH // NUM_RAYS + 1
                ray_x = ray * (WIDTH // NUM_RAYS)
                ray_y = (HEIGHT // 2) - (wall_h // 2)
                
                if TEX_BRICK and wall_type == TileType.WALL_BRICK.value:
                    diff_x = min(cx - math.floor(cx), math.ceil(cx) - cx)
                    diff_y = min(cy - math.floor(cy), math.ceil(cy) - cy)
                    tex_x = int((cy - math.floor(cy)) * tex_width) if diff_x < diff_y else int((cx - math.floor(cx)) * tex_width)
                    tex_x = tex_x % tex_width
                    
                    strip = TEX_BRICK.subsurface((tex_x, 0, 1, TEX_BRICK.get_height()))
                    strip_scaled = pygame.transform.scale(strip, (ray_w, int(wall_h)))
                    self.screen.blit(strip_scaled, (ray_x, ray_y))
                    
                    shade = max(0, min(255, int(dist * 12)))
                    if shade > 0:
                        s = pygame.Surface((ray_w, int(wall_h)))
                        s.set_alpha(shade)
                        self.screen.blit(s, (ray_x, ray_y))
                else:
                    color = (100, 100, 100) if wall_type == 2 else (139, 100, 50) if wall_type == 3 else (180, 50, 50)
                    shade = max(0, min(255, 255 - int(dist * 12)))
                    shaded_color = (min(color[0], shade), min(color[1], shade), min(color[2], shade))
                    pygame.draw.rect(self.screen, shaded_color, pygame.Rect(ray_x, ray_y, ray_w, wall_h))

    def draw_sprites(self):
        self.sprites.sort(key=lambda s: (self.px - s["x"])**2 + (self.py - s["y"])**2, reverse=True)
        
        for sprite in self.sprites:
            dx, dy = sprite["x"] - self.px, sprite["y"] - self.py
            dist = math.sqrt(dx**2 + dy**2)
            if dist < 0.2: continue
            
            angle = math.atan2(dy, dx) - self.p_angle
            while angle < -math.pi: angle += 2 * math.pi
            while angle > math.pi: angle -= 2 * math.pi
            
            if abs(angle) < FOV / 2 + 0.5:
                screen_x = int((0.5 * (angle / (FOV / 2)) + 0.5) * WIDTH)
                sprite_h = min(HEIGHT * 2, int(WALL_HEIGHT_MULTIPLIER / dist))
                sprite_w = sprite_h
                
                img = None
                if sprite["type"] == "bush": 
                    img = SPRITE_BUSH if sprite.get("var") == 1 else SPRITE_BUSH2
                elif sprite["type"] == "boss": 
                    img = SPRITE_BOSS_IDLE
                
                if img:
                    ray_index = int(screen_x / (WIDTH / NUM_RAYS))
                    if 0 <= ray_index < NUM_RAYS and dist < self.z_buffer[ray_index]:
                        scaled = pygame.transform.scale(img, (sprite_w, sprite_h))
                        self.screen.blit(scaled, (screen_x - sprite_w // 2, (HEIGHT // 2) - (sprite_h // 2)))

    def draw_projectiles(self):
        """Draw active projectiles in 3D space"""
        for proj in self.combat.active_projectiles:
            dx, dy = proj.x - self.px, proj.y - self.py
            dist = math.sqrt(dx**2 + dy**2)
            if dist < 0.2: continue
            
            angle = math.atan2(dy, dx) - self.p_angle
            while angle < -math.pi: angle += 2 * math.pi
            while angle > math.pi: angle -= 2 * math.pi
            
            if abs(angle) < FOV / 2 + 0.5:
                screen_x = int((0.5 * (angle / (FOV / 2)) + 0.5) * WIDTH)
                proj_h = min(HEIGHT, int(800 / dist))
                proj_w = proj_h // 2
                
                # Draw fireball as orange circle
                ray_index = int(screen_x / (WIDTH / NUM_RAYS))
                if 0 <= ray_index < NUM_RAYS and dist < self.z_buffer[ray_index]:
                    pygame.draw.circle(self.screen, (255, 150, 50), 
                                     (screen_x, int((HEIGHT // 2))), 
                                     max(3, int(proj_h // 4)))

    def draw_hud(self):
        bar_w, bar_h = 200, 20
        
        # Health bar
        pygame.draw.rect(self.screen, (50, 0, 0), (20, 20, bar_w, bar_h))
        pygame.draw.rect(self.screen, (255, 50, 50), (20, 20, bar_w * (self.health / self.max_health), bar_h))
        pygame.draw.rect(self.screen, (255, 255, 255), (20, 20, bar_w, bar_h), 2)
        
        health_text = self.font_small.render(f"HP: {int(self.health)}/{int(self.max_health)}", True, (255, 255, 255))
        self.screen.blit(health_text, (30, 25))
        
        # Mana bar
        pygame.draw.rect(self.screen, (0, 0, 50), (20, 50, bar_w, bar_h))
        pygame.draw.rect(self.screen, (50, 100, 255), (20, 50, bar_w * (self.mana / self.max_mana), bar_h))
        pygame.draw.rect(self.screen, (255, 255, 255), (20, 50, bar_w, bar_h), 2)
        
        mana_text = self.font_small.render(f"Mana: {int(self.mana)}/{int(self.max_mana)}", True, (255, 255, 255))
        self.screen.blit(mana_text, (30, 55))
        
        self.action_bar.draw(self.screen)
        self.inventory.draw(self.screen)

    def handle_spell_casting(self):
        """Handle keyboard input for spell casting"""
        keys = pygame.key.get_pressed()
        
        if keys[pygame.K_2]:  # Fireball
            success, proj, mana_used = self.combat.cast_spell("fireball", self.px, self.py, self.p_angle, self.mana)
            if success:
                self.mana -= mana_used
                self.mana = max(0, self.mana)
        
        if keys[pygame.K_3]:  # Heal
            success, _, mana_used = self.combat.cast_spell("heal", self.px, self.py, self.p_angle, self.mana)
            if success:
                self.mana -= mana_used
                self.health = min(self.max_health, self.health + self.combat.spells["heal"].heal_amount)
                self.mana = max(0, self.mana)

    def update_enemies(self):
        """Update all enemies and check for player collisions"""
        for enemy in self.enemies[:]:
            if not enemy.alive:
                self.enemies.remove(enemy)
                continue
            
            enemy.update(self.px, self.py)
            
            # Check for projectile collisions
            for proj in self.combat.active_projectiles:
                if proj.check_collision(enemy.x, enemy.y):
                    if enemy.take_damage(proj.damage):
                        proj.alive = False
                    else:
                        proj.alive = False

    def run(self):
        play_music("bgm")
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                    return
                elif e.type == pygame.KEYDOWN and (e.key == pygame.K_i or e.key == pygame.K_TAB):
                    self.inventory.toggle()

            if not self.inventory.visible:
                keys = pygame.key.get_pressed()
                ms = PLAYER_SPEED * dt
                dx, dy = 0, 0
                if keys[pygame.K_w]: dx, dy = math.cos(self.p_angle) * ms, math.sin(self.p_angle) * ms
                if keys[pygame.K_s]: dx, dy = -math.cos(self.p_angle) * ms, -math.sin(self.p_angle) * ms
                if keys[pygame.K_a]: dx, dy = math.cos(self.p_angle - math.pi/2) * ms, math.sin(self.p_angle - math.pi/2) * ms
                if keys[pygame.K_d]: dx, dy = math.cos(self.p_angle + math.pi/2) * ms, math.sin(self.p_angle + math.pi/2) * ms
                    
                if 0 <= int(self.px + dx) < MAP_SIZE and self.map[int(self.py)][int(self.px + dx)] == 0: self.px += dx
                if 0 <= int(self.py + dy) < MAP_SIZE and self.map[int(self.py + dy)][int(self.px)] == 0: self.py += dy
                    
                mx, my = pygame.mouse.get_rel()
                self.p_angle += mx * 0.002

            self.action_bar.update()
            self.combat.update()
            self.update_enemies()
            self.handle_spell_casting()
            
            # Regenerate mana slowly
            self.mana = min(self.max_mana, self.mana + 0.1)
            
            self.draw_raycast()
            self.draw_sprites()
            self.draw_projectiles()
            self.draw_hud()
            pygame.display.flip()

# ==========================================
#               MAIN MENU
# ==========================================
def show_main_menu():
    screen = pygame.display.set_mode((WIDTH, HEIGHT)) 
    pygame.display.set_caption("JPT RPG 3D - Main Menu")
    clock = pygame.time.Clock()
    font_med = pygame.font.SysFont("georgia", 24, bold=True)
    font_large = pygame.font.SysFont("georgia", 48, bold=True)
    
    rect_play = pygame.Rect(WIDTH//2 - 125, 250, 250, 60)
    rect_editor = pygame.Rect(WIDTH//2 - 125, 330, 250, 60)
    rect_boss = pygame.Rect(WIDTH//2 - 125, 410, 250, 60)
    rect_exit = pygame.Rect(WIDTH//2 - 125, 490, 250, 60)

    play_music("bgm")

    while True:
        pygame.mouse.set_visible(True)
        
        if BG_MENU: screen.blit(pygame.transform.scale(BG_MENU, (WIDTH, HEIGHT)), (0, 0))
        else: screen.fill((20, 20, 30))
        
        mouse_pos = pygame.mouse.get_pos()
        for e in pygame.event.get():
            if e.type == pygame.QUIT: sys.exit()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if rect_play.collidepoint(e.pos):
                    show_stat_screen()
                    screen = pygame.display.set_mode((WIDTH, HEIGHT))
                elif rect_editor.collidepoint(e.pos):
                    MapEditor().run()
                    screen = pygame.display.set_mode((WIDTH, HEIGHT))
                elif rect_boss.collidepoint(e.pos):
                    BossDesigner().run()
                    screen = pygame.display.set_mode((WIDTH, HEIGHT))
                elif rect_exit.collidepoint(e.pos):
                    sys.exit()

        title = font_large.render("JPT RPG 3D", True, (255, 200, 100))
        shadow = font_large.render("JPT RPG 3D", True, (0, 0, 0))
        screen.blit(shadow, (WIDTH//2 - title.get_width()//2 + 2, 120 + 2))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 120))

        buttons = [
            (rect_play, "Play Game", (50, 150, 50), (100, 255, 100)),
            (rect_editor, "Map Editor", (50, 50, 150), (100, 100, 255)),
            (rect_boss, "Boss Designer", (150, 100, 50), (255, 180, 100)),
            (rect_exit, "Exit Game", (150, 50, 50), (255, 100, 100))
        ]

        for rect, text, col_base, col_hover in buttons:
            hover = rect.collidepoint(mouse_pos)
            pygame.draw.rect(screen, col_hover if hover else col_base, rect)
            pygame.draw.rect(screen, (200, 200, 200), rect, 3)
            tsurf = font_med.render(text, True, (255, 255, 255))
            screen.blit(tsurf, (rect.centerx - tsurf.get_width()//2, rect.centery - tsurf.get_height()//2))

        pygame.display.flip()
        clock.tick(60)

def show_stat_screen():
    """Display stat allocation screen before starting game"""
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("JPT RPG 3D - Character Creation")
    clock = pygame.time.Clock()
    
    font_huge = pygame.font.SysFont("georgia", 60, bold=True)
    font_msg = pygame.font.SysFont("georgia", 20, bold=True)
    font_small = pygame.font.SysFont("georgia", 14, bold=True)
    
    stat_allocator = StatAllocator(font_huge, font_msg, font_small, WIDTH, HEIGHT)
    
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                sys.exit()
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return  # Back to menu
                elif e.key == pygame.K_c:
                    # Start game with allocated stats
                    game = Game(stat_allocator.get_stats())
                    game.run()
                    screen = pygame.display.set_mode((WIDTH, HEIGHT))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                stat_allocator.handle_click(e.pos)
        
        stat_allocator.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    show_main_menu()
