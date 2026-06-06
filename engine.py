import pygame
import json
import os
import random
import copy
from settings import *
from inventory import Inventory
from ui import ActionBar

class DummyChannel:
    def play(self, *args, **kwargs): pass
    def stop(self): pass
    def get_busy(self): return False
    def set_volume(self, vol): pass
    def fadeout(self, time): pass

try:
    pygame.mixer.init()
    CH_WALK = pygame.mixer.Channel(1)
    CH_RAIN = pygame.mixer.Channel(2)
    CH_CRICKETS = pygame.mixer.Channel(3)
    CH_TORCHES = pygame.mixer.Channel(4) 
    MIXER_READY = True
except Exception:
    CH_WALK = DummyChannel()
    CH_RAIN = DummyChannel()
    CH_CRICKETS = DummyChannel()
    CH_TORCHES = DummyChannel()
    MIXER_READY = False

def load_audio_safe(filename):
    if not MIXER_READY: return None
    try: return pygame.mixer.Sound(filename)
    except: return None

SFX_PICKUP = load_audio_safe("pickup.wav")
SFX_DOOR = load_audio_safe("door.wav")
SFX_ERROR = load_audio_safe("error.wav")
SFX_USE = load_audio_safe("use.wav")
SFX_WALK = load_audio_safe("walking.mp3")
SFX_RAIN = load_audio_safe("raining.mp3")
SFX_FIREBALL = load_audio_safe("shoot_fireball.wav")
SFX_DRINK = load_audio_safe("drink.wav")
SFX_CRICKETS = load_audio_safe("Midnight_crickets.mp3")
SFX_TORCH = load_audio_safe("torches_burning_sound.mp3") 
SFX_HIT_METALLIC = load_audio_safe("sword_hit_metallic.mp3")

class Game:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False) 
        # Force double buffering and hardware scaling to squeeze out more FPS
        #self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF | pygame.SCALED)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("RPGW3D Engine")
        self.clock = pygame.time.Clock()

        # Ensure a map attribute exists early so any helper called during init won't crash.
        # We try to use TileType / MAP_SIZE but fall back to a reasonable default if not available yet.
        try:
            self.map = [[TileType.EMPTY.value for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        except Exception:
            # Fallback: 50x50 zero map (safe placeholder)
            self.map = [[0 for _ in range(50)] for _ in range(50)]
        
        self.font = pygame.font.SysFont("georgia", 16) 
        self.font_msg = pygame.font.SysFont("georgia", 20, bold=True)
        self.font_small_bold = pygame.font.SysFont("georgia", 14, bold=True)
        self.font_massive = pygame.font.SysFont("georgia", 60, bold=True)
        self.font_massive_win = pygame.font.SysFont("georgia", 50, bold=True)
        
        self.game_over_overlay = pygame.Surface((WIDTH, HEIGHT))
        self.game_over_overlay.set_alpha(200)
        self.game_over_overlay.fill((100, 0, 0))
        
        self.level_complete_overlay = pygame.Surface((WIDTH, HEIGHT))
        self.level_complete_overlay.set_alpha(180)
        self.level_complete_overlay.fill((0, 0, 0))
        
        self.stat_points = 5
        self.strength = 10
        self.intelligence = 10
        self.endurance = 10
        self.show_stat_screen = False
        
        # --- FIX: Initialize game state before use ---
        self.recalculate_max_stats()
        self.health = self.max_health
        self.mana = self.max_mana
        self.stamina = self.max_stamina
        
        # --- FIX: Initialize player position and rotation ---
        self.player_x = (MAP_SIZE / 2) * TILE_SIZE
        self.player_y = (MAP_SIZE / 2) * TILE_SIZE
        self.player_angle = 0
        
        # --- FIX: Initialize inventory and action bar ---
        self.icons_dict = {}  # TODO: Load icons from asset files
        self.sfx_dict = {"door": SFX_DOOR, "pickup": SFX_PICKUP, "error": SFX_ERROR}
        self.inventory = Inventory(self.icons_dict, self.sfx_dict)
        self.action_bar = ActionBar(self.icons_dict)
        
        # --- FIX: Load map data ---
        self.map = self.get_initial_map_data()

    def get_initial_map_data(self):
        # Create a default map bordered by walls just in case the JSON fails
        default_map = [[TileType.EMPTY.value for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        for i in range(MAP_SIZE):
            default_map[0][i] = default_map[MAP_SIZE-1][i] = default_map[i][0] = default_map[i][MAP_SIZE-1] = TileType.WALL_BRICK.value
        
        try:
            if os.path.exists(MAP_DATA_FILE):
                with open(MAP_DATA_FILE, "r") as f:
                    data = json.load(f)
                    # Verify map dimensions match your settings
                    if len(data) == MAP_SIZE and len(data[0]) == MAP_SIZE:
                        print(f"Map successfully loaded from {MAP_DATA_FILE}.")
                        return data
                    else:
                        print("Map data size mismatch! Falling back to default map.")
        except Exception as e:
            print(f"Failed to load map data from {MAP_DATA_FILE}: {e}")
            
        return default_map

    def recalculate_max_stats(self):
        self.max_health = 50 + (self.endurance * 5)
        self.max_mana = 20 + (self.intelligence * 3)
        self.max_stamina = 50 + (self.endurance * 5)
        self.melee_dmg = 20 + int(self.strength * 1.5)
        self.magic_dmg = 25 + int(self.intelligence * 2.0)

    def draw_stat_screen(self):
        """Render the stat allocation screen"""
        self.screen.fill((20, 20, 30))
        
        title = self.font_massive.render("ALLOCATE STATS", True, (200, 150, 0))
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 50))
        
        points_text = self.font_msg.render(f"Points Available: {self.stat_points}", True, (100, 200, 100))
        self.screen.blit(points_text, (50, 150))
        
        y_offset = 220
        stat_names = ["Strength", "Intelligence", "Endurance"]
        stat_values = [self.strength, self.intelligence, self.endurance]
        
        for i, (name, value) in enumerate(zip(stat_names, stat_values)):
            stat_text = self.font_msg.render(f"{name}: {value}", True, (255, 255, 255))
            self.screen.blit(stat_text, (100, y_offset + i * 80))
        
        info = self.font.render("Press C to close | TODO: Add stat allocation buttons", True, (150, 150, 150))
        self.screen.blit(info, (50, 500))

    def run(self):
        running = True
        while running:
            if self.show_stat_screen:
                for e in pygame.event.get():
                    if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                        running = False
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_c:
                        self.show_stat_screen = False

                self.draw_stat_screen()
                pygame.display.flip()
                self.clock.tick(FPS)
                continue
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_c:
                        self.show_stat_screen = True
                    elif e.key == pygame.K_i:
                        self.inventory.toggle()

            # --- FIX: Update game state ---
            self.action_bar.update()

            # --- FIX: Render game ---
            self.screen.fill((30, 30, 40))
            
            # TODO: Render map, player, enemies, particles, effects, etc.
            
            # Render UI layers
            self.action_bar.draw(self.screen)
            self.inventory.draw(self.screen, pygame.mouse.get_pos(), self.font)
            
            pygame.display.flip()
            self.clock.tick(FPS)
