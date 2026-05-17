import shutil
import os

source1 = r"C:\Users\hp\.gemini\antigravity\brain\022a7ac1-668c-4f04-9e1f-7d8f43563922\premium_flat_lay_tshirt_1777999633381.png"
source2 = r"C:\Users\hp\.gemini\antigravity\brain\022a7ac1-668c-4f04-9e1f-7d8f43563922\premium_model_mockup_1778000090728.png"

dest_dir = r"e:\etsy related product\mockups\static\mockups\images"
os.makedirs(dest_dir, exist_ok=True)

try:
    shutil.copy(source1, os.path.join(dest_dir, "flat_lay.png"))
    shutil.copy(source2, os.path.join(dest_dir, "model.png"))
    print("Files copied successfully!")
except Exception as e:
    print(f"Error: {e}")
