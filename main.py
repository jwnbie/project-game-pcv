import cv2
import numpy as np
import random
import time
import math
import winsound
import threading

# 1. Initialization and Setup
cap = cv2.VideoCapture(0)
frame_w, frame_h = 640, 480
cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_w)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_h)

window_name = "Shark Attack"
cv2.namedWindow(window_name)
cv2.namedWindow("Hand Segment")
cv2.namedWindow("Live Hand Feed")

cv2.moveWindow(window_name, 20, 40)
cv2.moveWindow("Live Hand Feed", 690, 40)
cv2.moveWindow("Hand Segment", 690, 560)

# 2. Audio Pipeline Initialization
try:
    winsound.PlaySound("sound/bubbles.wav", winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC)
except:
    pass

welcome_img = cv2.imread('assets/welcome.png')
if welcome_img is not None:
    welcome_screen = cv2.resize(welcome_img, (frame_w, frame_h))
    cv2.imshow(window_name, welcome_screen)
    cv2.waitKey(2000) 

def play_bgm_loop():
    try:
        winsound.PlaySound("sound/music.wav", winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
    except:
        pass

bgm_thread = threading.Thread(target=play_bgm_loop)
bgm_thread.daemon = True
bgm_thread.start()

# 3. Image Segmentation & Noise Cleaning
def manual_erode(mask, kernel_size=5):
    pad = kernel_size // 2
    shifted_masks = []
    for y in range(-pad, pad + 1):
        for x in range(-pad, pad + 1):
            shifted_masks.append(np.roll(np.roll(mask, y, axis=0), x, axis=1))
    return np.all(np.array(shifted_masks) == 255, axis=0).astype(np.uint8) * 255

def manual_dilate(mask, kernel_size=5):
    pad = kernel_size // 2
    shifted_masks = []
    for y in range(-pad, pad + 1):
        for x in range(-pad, pad + 1):
            shifted_masks.append(np.roll(np.roll(mask, y, axis=0), x, axis=1))
    return np.any(np.array(shifted_masks) == 255, axis=0).astype(np.uint8) * 255

def overlay_sprite(background, sprite, center_x, center_y):
    bg_h, bg_w, _ = background.shape
    sp_h, sp_w, sp_c = sprite.shape
    x1, y1 = int(center_x - sp_w / 2), int(center_y - sp_h / 2)
    x2, y2 = x1 + sp_w, y1 + sp_h

    if x1 < 0 or y1 < 0 or x2 > bg_w or y2 > bg_h:
        return background

    roi = background[y1:y2, x1:x2]
    if sp_c == 4: 
        alpha = np.expand_dims(sprite[:, :, 3] / 255.0, axis=2)
        blended = sprite[:, :, :3] * alpha + roi * (1.0 - alpha)
        background[y1:y2, x1:x2] = blended.astype(np.uint8)
    else:
        background[y1:y2, x1:x2] = sprite[:, :, :3]
    return background

def draw_ui(img, text, pos, font_scale, color):
    x, y = pos
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_DUPLEX, font_scale, (0, 0, 0), 5, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_DUPLEX, font_scale, color, 2, cv2.LINE_AA)

def draw_heart(img, center_x, center_y, size=15, color=(90, 90, 255)):
    cv2.circle(img, (center_x - size//2, center_y - size//4), size//2, color, -1, cv2.LINE_AA)
    cv2.circle(img, (center_x + size//2, center_y - size//4), size//2, color, -1, cv2.LINE_AA)
    triangle_points = np.array([
        [center_x - size, center_y - size//6],
        [center_x + size, center_y - size//6],
        [center_x, center_y + size]
    ], np.int32)
    cv2.fillPoly(img, [triangle_points], color, cv2.LINE_AA)

bg_sea = cv2.resize(cv2.imread('assets/sea.jpg'), (frame_w, frame_h))
small_w, small_h = 55, 40
small_fish_base = cv2.resize(cv2.imread('assets/small_fish.png', cv2.IMREAD_UNCHANGED), (small_w, small_h))
shark_base_w, shark_base_h = 250, 170
shark_img_base = cv2.resize(cv2.imread('assets/shark.png', cv2.IMREAD_UNCHANGED), (shark_base_w, shark_base_h))
score_place_img = cv2.resize(cv2.imread('assets/score_place.png', cv2.IMREAD_UNCHANGED), (180, 65))
player_master_img = cv2.imread('assets/sword.png', cv2.IMREAD_UNCHANGED)

score = 0
lives = 3
zone_x1, zone_y1, zone_x2, zone_y2 = 300, 40, 620, 440

# Slightly increased weapon dimensions while preserving vertical scaling format
player_base_w, player_base_h = 85, 155
SMOOTH_FACTOR = 0.20 
SIZE_SMOOTH_FACTOR = 0.10 

smooth_x, smooth_y = frame_w // 2, frame_h // 2
smooth_w, smooth_h = player_base_w, player_base_h

chomp_timer = 0
chomp_x, chomp_y = 0, 0
escape_text_timer = 0

last_hit_time = 0
invulnerable_duration = 1.5  

bubbles = [{'x': random.randint(10, frame_w - 10), 'y': random.randint(50, frame_h - 10), 
            'radius': random.randint(2, 7), 'speed_y': random.uniform(1.5, 3.5)} for _ in range(10)]

small_fishes = []
for _ in range(15):
    direction = random.choice([0, 1])
    small_fishes.append({
        'x': random.randint(frame_w, frame_w + 300) if direction == 0 else random.randint(-300, -60),
        'y': random.randint(50, frame_h - 50),
        'speed': random.randint(2, 4), 
        'dir': direction
    })

sharks = []
for i in range(3):
    direction = random.choice([0, 1])
    spawn_x = (frame_w + 150 + (i * 450)) if direction == 0 else (-250 - (i * 450))
    sharks.append({
        'x': spawn_x,
        'y': random.randint(280, frame_h - 70),  
        'speed': random.randint(1, 2), 
        'dir': direction
    })

player_x, player_y = frame_w // 2, frame_h // 2
prev_player_x = player_x
player_facing_right = True 

# Core Gameplay Loop
while cap.isOpened() and lives > 0:
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1) 
    
    current_time = time.time()
    
    roi_frame = frame[zone_y1:zone_y2, zone_x1:zone_x2]
    hsv = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)
    lower_skin = np.array([0, 30, 60], dtype=np.uint8)
    upper_skin = np.array([20, 255, 255], dtype=np.uint8)
    
    mask_roi = np.where(
        (hsv[:,:,0] >= lower_skin[0]) & (hsv[:,:,0] <= upper_skin[0]) &
        (hsv[:,:,1] >= lower_skin[1]) & (hsv[:,:,1] <= upper_skin[1]) &
        (hsv[:,:,2] >= lower_skin[2]) & (hsv[:,:,2] <= upper_skin[2]),
        255, 0
    ).astype(np.uint8)
    
    mask_roi = manual_erode(mask_roi, kernel_size=5)
    mask_roi = manual_dilate(mask_roi, kernel_size=5)

    hand_feed_display = roi_frame.copy()

    y_indices, x_indices = np.where(mask_roi == 255)
    total_skin = len(x_indices)
    
    target_w, target_h = player_base_w, player_base_h
    is_eating = False  
    gesture_angka_1 = False

    # 4. Bounding Box & Vertical Split Gesture Detection
    if total_skin > 500: 
        raw_x = int(np.mean(x_indices))
        raw_y = int(np.mean(y_indices))
        
        target_x = int((raw_x / (zone_x2 - zone_x1)) * frame_w)
        target_y = int((raw_y / (zone_y2 - zone_y1)) * frame_h)

        min_x, max_x = np.min(x_indices), np.max(x_indices)
        min_y, max_y = np.min(y_indices), np.max(y_indices)
        hand_w = max_x - min_x + 1
        hand_h = max_y - min_y + 1
        
        split_line = min_y + int(hand_h * 0.35)
        top_pixels = np.sum(mask_roi[min_y:split_line, min_x:max_x] == 255)
        bottom_pixels = np.sum(mask_roi[split_line:max_y, min_x:max_x] == 255)
        
        if hand_h > int(hand_w * 1.25) and top_pixels > 0:
            pixel_ratio = bottom_pixels / top_pixels
            if pixel_ratio > 2.8:  
                gesture_angka_1 = True
                escape_text_timer = 12

        # 5. Movement Smoothing & Action Mechanics
        smooth_x = int((smooth_x * (1 - SMOOTH_FACTOR)) + (target_x * SMOOTH_FACTOR))
        
        if gesture_angka_1:
            smooth_y = int((smooth_y * 0.6) + (60 * 0.4)) 
        else:
            smooth_y = int((smooth_y * (1 - SMOOTH_FACTOR)) + (target_y * SMOOTH_FACTOR))

        if smooth_x > prev_player_x + 2:   
            player_facing_right = True
        elif smooth_x < prev_player_x - 2: 
            player_facing_right = False
            
        prev_player_x = smooth_x

        if not gesture_angka_1:
            x_spread = np.std(x_indices) if len(x_indices) > 0 else 0
            if x_spread < 35: 
                # Size constraints verified; values remain static to prevent image skewing
                target_w, target_h = player_base_w, player_base_h
                is_eating = True 

        cv2.rectangle(hand_feed_display, (min_x, min_y), (max_x, max_y), (0, 255, 0), 2)

    smooth_w = int((smooth_w * (1 - SIZE_SMOOTH_FACTOR)) + (target_w * SIZE_SMOOTH_FACTOR))
    smooth_h = int((smooth_h * (1 - SIZE_SMOOTH_FACTOR)) + (target_h * SIZE_SMOOTH_FACTOR))

    player_x = max(70, min(smooth_x, frame_w - 70))
    player_y = max(55, min(smooth_y, frame_h - 55))

    screen = bg_sea.copy()

    if random.random() < 0.30:  
        bubbles.append({'x': random.randint(10, frame_w - 10), 'y': frame_h + random.randint(5, 20),
                        'radius': random.randint(2, 7), 'speed_y': random.uniform(1.5, 4.0)})

    if gesture_angka_1 or escape_text_timer > 0:
        for _ in range(2):
            bubbles.append({'x': player_x + random.randint(-35, 35), 'y': player_y + random.randint(30, 60),
                            'radius': random.randint(1, 4), 'speed_y': random.randint(4, 9)})

    remained_bubbles = []
    for b in bubbles:
        b['y'] -= b['speed_y']            
        b['x'] += random.randint(-1, 1)    
        if b['y'] > 10:
            remained_bubbles.append(b)
            cv2.circle(screen, (b['x'], int(b['y'])), b['radius'], (235, 230, 220), 1, cv2.LINE_AA)
    bubbles = remained_bubbles

    for fish in small_fishes:
        if fish['dir'] == 0: 
            fish['x'] -= fish['speed']
            if fish['x'] < -60: 
                fish['x'] = frame_w + random.randint(20, 150)
                fish['y'] = random.randint(50, frame_h - 50)
                fish['dir'] = random.choice([0, 1])
        else: 
            fish['x'] += fish['speed']
            if fish['x'] > frame_w + 60: 
                fish['x'] = -random.randint(20, 150)
                fish['y'] = random.randint(50, frame_h - 50)
                fish['dir'] = random.choice([0, 1])

        sprite_small = small_fish_base.copy()
        if fish['dir'] == 1: 
            sprite_small = sprite_small[:, ::-1, :]

        dynamic_hitbox = max(85, int(smooth_w * 0.65))
        dist_to_small = np.sqrt((player_x - fish['x'])**2 + (player_y - fish['y'])**2)
        
        if dist_to_small < dynamic_hitbox: 
            if is_eating:
                score += 10
                
                chomp_x, chomp_y = player_x - 40, player_y - 65
                chomp_timer = 12 
                
                fish['dir'] = random.choice([0, 1])
                fish['x'] = frame_w + random.randint(20, 150) if fish['dir'] == 0 else -random.randint(20, 150)
                fish['y'] = random.randint(50, frame_h - 50)
                continue

        screen = overlay_sprite(screen, sprite_small, fish['x'], fish['y'])

    if chomp_timer > 0:
        draw_ui(screen, "SLASH!", (chomp_x, chomp_y), 0.6, (0, 220, 255))
        chomp_timer -= 1 

    if escape_text_timer > 0:
        draw_ui(screen, "ESCAPE DASH!!", (player_x - 80, player_y + 60), 0.65, (0, 255, 100))
        escape_text_timer -= 1

    # 6. Hazard Constraint & Collision Handling
    for shark in sharks:
        if shark['dir'] == 0: 
            shark['x'] -= shark['speed']
            if shark['y'] < max(280, player_y): shark['y'] += 1
            if shark['y'] > player_y and shark['y'] > 280: shark['y'] -= 1
            
            if shark['x'] < -260: 
                shark['dir'] = random.choice([0, 1])
                shark['x'] = frame_w + 150 + random.randint(300, 600) if shark['dir'] == 0 else -250 - random.randint(300, 600)
                shark['y'] = random.randint(280, frame_h - 70)
        else: 
            shark['x'] += shark['speed']
            if shark['y'] < max(280, player_y): shark['y'] += 1
            if shark['y'] > player_y and shark['y'] > 280: shark['y'] -= 1
            
            if shark['x'] > frame_w + 260: 
                shark['dir'] = random.choice([0, 1])
                shark['x'] = frame_w + 150 + random.randint(300, 600) if shark['dir'] == 0 else -250 - random.randint(300, 600)
                shark['y'] = random.randint(280, frame_h - 70)

        sprite_shark = shark_img_base.copy()
        if shark['dir'] == 1: 
            sprite_shark = sprite_shark[:, ::-1, :]

        dist_to_shark = np.sqrt((player_x - shark['x'])**2 + (player_y - shark['y'])**2)
        if dist_to_shark < 85: 
            if current_time - last_hit_time > invulnerable_duration:
                lives -= 1
                last_hit_time = current_time  
                shark['x'] += int(shark['speed'] * 120) if shark['dir'] == 1 else -int(shark['speed'] * 120)
            continue

        screen = overlay_sprite(screen, sprite_shark, shark['x'], shark['y'])

    player_img = cv2.resize(player_master_img, (player_base_w, player_base_h))
    active_player_sprite = cv2.resize(player_img, (smooth_w, smooth_h))
    if player_facing_right:
        active_player_sprite = active_player_sprite[:, ::-1, :] 

    if current_time - last_hit_time < invulnerable_duration:
        if int((current_time - last_hit_time) * 10) % 2 == 0:
            screen = overlay_sprite(screen, active_player_sprite, player_x, player_y)
    else:
        screen = overlay_sprite(screen, active_player_sprite, player_x, player_y)

    screen = overlay_sprite(screen, score_place_img, 105, 45)
    draw_ui(screen, f"{score:04d}", (65, 48), 0.9, (255, 255, 255))
    
    for i in range(lives):
        draw_heart(screen, center_x=490 + (i * 45), center_y=42, size=15, color=(90, 90, 255))

    cv2.imshow(window_name, screen)
    cv2.imshow("Hand Segment", mask_roi) 
    cv2.imshow("Live Hand Feed", hand_feed_display) 

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Clean up video capture resources and windows
cap.release()
cv2.destroyAllWindows()

# 7. Instant Game Over Screen
if lives <= 0:
    game_over_img = cv2.imread('assets/game_over.png')
    if game_over_img is not None:
        game_over_screen = cv2.resize(game_over_img, (frame_w, frame_h))
    else:
        game_over_screen = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        draw_ui(game_over_screen, "GAME OVER", (175, 220), 1.8, (0, 0, 255))
        
    draw_ui(game_over_screen, f"SCORE : {score:04d}", (235, 410), 0.85, (255, 255, 255))
    
    cv2.imshow(window_name, game_over_screen)
    cv2.waitKey(1)  
    
    try:
        winsound.PlaySound("sound/lose.wav", winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC)
    except:
        pass
        
    cv2.waitKey(4000) 
    cv2.destroyAllWindows()
