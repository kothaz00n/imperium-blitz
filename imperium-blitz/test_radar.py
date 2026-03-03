from PIL import Image, ImageDraw, ImageChops
import os

# CONFIG (MATCHING OVERLAY.PY)
VIEWPORT = {"x1": 14, "y1": 180, "x2": 695, "y2": 705}
TEAMS = {
    "NPC": {"color": "yellow", "crossings": 2},
    "PLAYER": {"color": "#00ffff", "crossings": 2}
}

# BOX DIMENSIONS CONFIGURATION
BOX_WIDTH = 20
BOX_HEIGHT = 20

def process_image(img):
    """Standard Hue/Saturation Detection Logic (Copied from overlay.py)"""
    w, h = img.size
    r, g, b = img.split()
    
    # 1. PLAYER MASK (Cyan/Blue)
    max_rg = ImageChops.lighter(r, g)
    diff_blue = ImageChops.subtract(b, max_rg)
    # Note: Threshold fixed to 25 as per latest code
    mask_player = diff_blue.point(lambda x: 255 if x > 25 else 0, mode='1')
    
    # 2. NPC MASK (White/Gray)
    lum = img.convert("L")
    mask_bright = lum.point(lambda x: 255 if x > 150 else 0, mode='1')
    
    diff_rg = ImageChops.difference(r, g)
    diff_rb = ImageChops.difference(r, b)
    diff_gb = ImageChops.difference(g, b)
    saturation = ImageChops.add(ImageChops.add(diff_rg, diff_rb), diff_gb)
    mask_low_sat = saturation.point(lambda x: 255 if x < 40 else 0, mode='1')
    
    mask_npc = ImageChops.multiply(mask_bright, mask_low_sat)
    
    # DEBUG SAVES
    mask_player.save("debug_mask_player.png")
    mask_bright.save("debug_mask_bright.png")
    mask_low_sat.save("debug_mask_low_sat.png")
    mask_npc.save("debug_mask_npc.png")
    
    print("Debug masks saved.")

    new_candidates = []
    
    # 3. SCANNING
    targets = [("NPC", mask_npc), ("PLAYER", mask_player)]
    for t_type, mask in targets:
        pix = mask.load()
        visited = set()
        
        # Test mode: Scan closely (step 2) to ensure we catch everything
        scan_step = 2 
            
        for y in range(0, h, scan_step):
            for x in range(0, w, scan_step):
                if pix[x, y] > 0 and (x, y) not in visited:
                    stack = [(x, y)]; visited.add((x, y))
                    min_x, max_x, min_y, max_y = x, x, y, y
                    count = 0
                    
                    while stack:
                        cx, cy = stack.pop(); count += 1
                        min_x, max_x = min(min_x, cx), max(max_x, cx)
                        min_y, max_y = min(min_y, cy), max(max_y, cy)
                        
                        for dx, dy in [(-5,0), (5,0), (0,-2), (0,2)]: 
                            nx, ny = cx+dx, cy+dy
                            if 0 <= nx < w and 0 <= ny < h and pix[nx, ny] > 0 and (nx, ny) not in visited:
                                visited.add((nx, ny)); stack.append((nx, ny))
                        if count > 1200: break 
                    
                    cw, ch = max_x - min_x, max_y - min_y
                    if 10 < cw < 250 and 6 < ch < 30:
                            density = count / (cw * ch)
                            if 0.1 < density < 0.65:
                                mid_y = min_y + (ch // 2)
                                crossings = 0
                                last = 0
                                for sx in range(min_x, max_x, 2):
                                    val = pix[sx, mid_y]
                                    if val > 0 and last == 0: crossings += 1
                                    last = val
                                
                                if crossings >= TEAMS[t_type]["crossings"]:
                                    cx, cy = min_x + cw//2, min_y + ch//2
                                    new_candidates.append({'cx': cx, 'cy': cy, 'type': t_type, 'w': cw, 'h': ch}) # Added w/h for debug drawing

    return new_candidates

def run_test():
    img_path = r"C:\Users\Franc\.gemini\antigravity\brain\0922aae0-4ae8-40c7-adce-2819f106f970\uploaded_media_1769992493604.png"
    
    if not os.path.exists(img_path):
        print(f"Error: Image not found at {img_path}")
        return

    print(f"Loading image: {img_path}")
    full_img = Image.open(img_path).convert("RGB")
    
    print(f"Image Size: {full_img.size}")
    
    # Check if image is large enough for viewport crop
    if full_img.width >= VIEWPORT["x2"] and full_img.height >= VIEWPORT["y2"]:
        crop_area = (VIEWPORT["x1"], VIEWPORT["y1"], VIEWPORT["x2"], VIEWPORT["y2"])
        print(f"Cropping to viewport: {crop_area}")
        viewport_img = full_img.crop(crop_area)
    else:
        print("Image is smaller than expected viewport. Analyzing FULL image.")
        viewport_img = full_img

    print("Running detection...")
    candidates = process_image(viewport_img)
    print(f"Found {len(candidates)} candidates.")

    # Draw results
    draw = ImageDraw.Draw(viewport_img)
    
    print("Results:")
    for c in candidates:
        print(f" - {c['type']} at ({c['cx']}, {c['cy']})")
        color = TEAMS[c['type']]["color"]
        # Draw 16x16 box
        cx, cy = c['cx'], c['cy']
        # Draw box with configured dimensions
        half_w = BOX_WIDTH // 2
        half_h = BOX_HEIGHT // 2
        draw.rectangle([cx-half_w, cy-half_h, cx+half_w, cy+half_h], outline=color, width=2)
        # Draw Text
        draw.text((cx, cy-20), c['type'], fill=color)

    output_path = "radar_test_result.png"
    viewport_img.save(output_path)
    print(f"Saved result to {output_path}")

if __name__ == "__main__":
    run_test()
