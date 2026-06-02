from PIL import Image
import os

assets_path = r"D:\project\frontend\src\assets"
icon_png = os.path.join(assets_path, "icon.png")

if os.path.exists(icon_png):
    img = Image.open(icon_png)
    width, height = img.size
    blue_pixels = 0
    for x in range(width):
        for y in range(height):
            pixel = img.getpixel((x, y))
            # Scan for blue swoosh color (e.g., cyan/blue highlights: G > 100, B > 180, R < 100)
            if isinstance(pixel, tuple):
                r, g, b = pixel[0], pixel[1], pixel[2]
                if b > 150 and g > 80 and r < 120:
                    blue_pixels += 1
            else:
                if pixel > 150:
                    blue_pixels += 1
                    
    print(f"icon.png: size={img.size}, blue_pixels={blue_pixels}")
else:
    print("icon.png does not exist")
