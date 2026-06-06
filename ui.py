import pygame
from settings import *

class ActionBar:
    def __init__(self, icons_dict):
        self.icons = icons_dict
        # Expanded to 6 slots for that MMO feel!
        self.slots = [
            {"key": pygame.K_1, "label": "1", "name": "Empty", "icon": None, "cd": 0, "max_cd": 30, "type": "none", "cost": 0},
            {"key": pygame.K_2, "label": "2", "name": "Fireball", "icon": icons_dict.get("fireball"), "cd": 0, "max_cd": 60, "type": "magic", "cost": 10},
            {"key": pygame.K_3, "label": "3", "name": "Empty", "icon": None, "cd": 0, "max_cd": 120, "type": "none", "cost": 0},
            {"key": pygame.K_4, "label": "4", "name": "Empty", "icon": None, "cd": 0, "max_cd": 10, "type": "none", "cost": 0},
            {"key": pygame.K_5, "label": "5", "name": "Empty", "icon": None, "cd": 0, "max_cd": 10, "type": "none", "cost": 0},
            {"key": pygame.K_6, "label": "6", "name": "Empty", "icon": None, "cd": 0, "max_cd": 10, "type": "none", "cost": 0}
        ]
        self.font = pygame.font.SysFont("georgia", 14, bold=True)
        self.slot_size = 50
        self.spacing = 10

    def set_slot(self, index, name, icon, action_type, max_cd=30, cost=0):
        if 0 <= index < len(self.slots):
            self.slots[index]["name"] = name
            self.slots[index]["icon"] = icon
            self.slots[index]["type"] = action_type
            self.slots[index]["max_cd"] = max_cd
            self.slots[index]["cost"] = cost

    def swap_slots(self, idx1, idx2):
        s1, s2 = self.slots[idx1], self.slots[idx2]
        # Swap everything EXCEPT the hotkey and label so the keys don't get scrambled!
        s1["name"], s2["name"] = s2["name"], s1["name"]
        s1["icon"], s2["icon"] = s2["icon"], s1["icon"]
        s1["type"], s2["type"] = s2["type"], s1["type"]
        s1["cd"], s2["cd"] = s2["cd"], s1["cd"]
        s1["max_cd"], s2["max_cd"] = s2["max_cd"], s1["max_cd"]
        s1["cost"], s2["cost"] = s2["cost"], s1["cost"]

    def clear_slot(self, index):
        self.set_slot(index, "Empty", None, "none", 10, 0)

    def get_slot_at(self, pos):
        total_width = (len(self.slots) * self.slot_size) + ((len(self.slots) - 1) * self.spacing)
        start_x = (WIDTH // 2) - (total_width // 2)
        start_y = HEIGHT - self.slot_size - 20 
        for i in range(len(self.slots)):
            x = start_x + (i * (self.slot_size + self.spacing))
            rect = pygame.Rect(x, start_y, self.slot_size, self.slot_size)
            if rect.collidepoint(pos):
                return i
        return None

    def update(self):
        for slot in self.slots:
            if slot["cd"] > 0: slot["cd"] -= 1

    def draw(self, screen):
        total_width = (len(self.slots) * self.slot_size) + ((len(self.slots) - 1) * self.spacing)
        start_x = (WIDTH // 2) - (total_width // 2)
        start_y = HEIGHT - self.slot_size - 20 

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
                cd_height = int(self.slot_size * cd_ratio)
                overlay = pygame.Surface((self.slot_size, cd_height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180)) 
                screen.blit(overlay, (x, start_y + (self.slot_size - cd_height)))

            label_surf = self.font.render(slot["label"], True, (255, 255, 255))
            screen.blit(label_surf, (x + 4, start_y + 2))