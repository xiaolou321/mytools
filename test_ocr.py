from PIL import Image, ImageDraw
import io
import sys
from ocr_engine import recognize_text_from_bytes

def run_test():
    print(f"Current platform: {sys.platform}")
    
    # 1. Create a simple image containing clear text
    # We will draw a black text on a white background
    img = Image.new('RGB', (400, 150), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Draw simple words
    d.text((20, 30), "OCR Testing Output", fill=(0, 0, 0))
    d.text((20, 70), "Hello World from Python", fill=(0, 0, 0))
    
    # Save image to bytes in memory
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    image_bytes = buf.getvalue()
    
    print("Image created. Running OCR engine...")
    
    # 2. Recognize text
    result = recognize_text_from_bytes(image_bytes)
    
    print("\n--- OCR RESULTS ---")
    print(result)
    print("-------------------")
    
    # Check if the result is correct
    if "OCR" in result or "Hello" in result or "Testing" in result:
        print("Success! Native OCR is working correctly.")
        sys.exit(0)
    else:
        print("Warning: OCR did not return expected text. Please verify engine capability.")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
