#!/usr/bin/env python3
"""
Local test script for the Photo Frame Generator Cloud Function
This script tests the full pipeline including Gemini API integration
"""

import os
import sys
from PIL import Image, ImageDraw
import requests
import google.generativeai as genai
from pathlib import Path

def setup_gemini_api():
    """Setup and configure Gemini API"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        print("Set it with: export GEMINI_API_KEY='your_api_key_here'")
        return None
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-vision')
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return None

def test_gemini_analysis(image_path):
    """Test Gemini API with a real image"""
    try:
        print(f"Testing Gemini API with image: {image_path}")
        
        # Load the image
        image = Image.open(image_path)
        print(f"Image loaded: {image.size[0]}x{image.size[1]} pixels, mode: {image.mode}")
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
            print("Converted image to RGB mode")
        
        # Create a prompt for image analysis
        prompt = """
        Analyze this image and check for anything that's wrong.
        If there's something wrong, anaylze if the thing that's broken is a software related issue or something else.
        If it's a software related issue, return "yes", otherwise return "no".
        Only return "yes" or "no", no other text
        """
        
        print("Sending image to Gemini API for analysis...")
        
        # Generate content with Gemini
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content([prompt, image])
        
        # Extract the suggested style
        analyze_result = response.text.strip().lower()
        print(f"Gemini API response: '{response.text.strip()}'")
            
    except Exception as e:
        print(f"Error analyzing image with Gemini: {e}")
        analyze_result = "no"  # Default to "no" on error

    if analyze_result == "yes":
        print("Software related issue detected")
        # Load the yes frame and create composite
        result_image = create_framed_image(image, "yes.png")
        result_image.save("test_yes.png")
        print("Saved result as test_yes.png")
    else:
        print("No software related issue detected")
        # Load the no frame and create composite
        result_image = create_framed_image(image, "no.png")
        result_image.save("test_no.png")
        print("Saved result as test_no.png")

def create_framed_image(user_image, frame_path):
    """Create a composite image with the user image fitted into the frame"""
    try:
        # Load the frame (yes.png or no.png)
        frame = Image.open(frame_path)
        print(f"Frame loaded: {frame.size[0]}x{frame.size[1]} pixels")
        
        # Convert frame to RGBA if it isn't already (for transparency support)
        if frame.mode != 'RGBA':
            frame = frame.convert('RGBA')
        
        # Get frame dimensions
        frame_width, frame_height = frame.size
        
        # Calculate the area where we want to place the user image
        # Assuming we want to fit the image in the center with some padding
        padding = 50  # Adjust this based on your frame design
        target_width = frame_width - (2 * padding)
        target_height = frame_height - (2 * padding)
        
        # Resize user image to fit within the target area while maintaining aspect ratio
        user_image_resized = resize_image_to_fit(user_image, target_width, target_height)
        
        # Create a new image with the frame size and white background
        result = Image.new('RGBA', (frame_width, frame_height), (255, 255, 255, 255))
        
        # Calculate position to center the user image
        user_width, user_height = user_image_resized.size
        x_offset = (frame_width - user_width) // 2
        y_offset = (frame_height - user_height) // 2
        
        # Paste the user image onto the result
        result.paste(user_image_resized, (x_offset, y_offset))
        
        # Paste the frame on top (this will overlay the frame graphics)
        result = Image.alpha_composite(result, frame)
        
        # Convert back to RGB for saving as JPEG/PNG
        final_result = Image.new('RGB', result.size, (255, 255, 255))
        final_result.paste(result, mask=result.split()[-1] if result.mode == 'RGBA' else None)
        
        return final_result
        
    except Exception as e:
        print(f"Error creating framed image: {e}")
        return user_image

def resize_image_to_fit(image, target_width, target_height):
    """Resize image to fit within target dimensions while maintaining aspect ratio"""
    original_width, original_height = image.size
    
    # Calculate scaling ratios
    width_ratio = target_width / original_width
    height_ratio = target_height / original_height
    
    # Use the smaller ratio to ensure the image fits within bounds
    scale_ratio = min(width_ratio, height_ratio)
    
    # Calculate new dimensions
    new_width = int(original_width * scale_ratio)
    new_height = int(original_height * scale_ratio)
    
    # Resize the image
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    print(f"Resized image from {original_width}x{original_height} to {new_width}x{new_height}")
    
    return resized_image



def main():
    setup_gemini_api()
    # image_path = "test.JPG"
    image_path = "test2.jpg"
    test_gemini_analysis(image_path)

if __name__ == "__main__":
    main()
