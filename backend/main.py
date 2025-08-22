import functions_framework
import os
import base64
import json
import tempfile
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
from google.cloud import storage
import uuid
from datetime import datetime, timedelta

# Configure Gemini API
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

# Initialize Gemini model
model = genai.GenerativeModel('gemini-1.5-pro-latest')

# Initialize Google Cloud Storage client
storage_client = storage.Client()
bucket_name = os.environ.get('GCS_BUCKET_NAME', 'photo-frame-bucket')
bucket = storage_client.bucket(bucket_name)

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

def analyze_image_with_gemini(image):
    """Use Gemini API to analyze the image for software issues"""
    try:
        # Create a prompt for image analysis
        prompt = """
        Analyze this image and check for anything that's wrong.
        If there's something wrong, analyze if the thing that's broken is a software related issue or something else.
        If it's a software related issue, return "yes", otherwise return "no".
        Only return "yes" or "no", no other text
        """
        
        print("Sending image to Gemini API for analysis...")
        
        # Generate content with Gemini
        response = model.generate_content([prompt, image])
        
        # Extract the analysis result
        analyze_result = response.text.strip().lower()
        print(f"Gemini API response: '{response.text.strip()}'")
        
        return analyze_result
            
    except Exception as e:
        print(f"Error analyzing image with Gemini: {e}")
        # Default to "no" on error
        return "no"

def upload_to_gcs(image, filename):
    """Upload the processed image to Google Cloud Storage"""
    try:
        # Save image to temporary file with WebP for better compression
        with tempfile.NamedTemporaryFile(suffix='.webp', delete=False) as temp_file:
            image.save(temp_file.name, 'WEBP', quality=85, optimize=True)
            temp_file_path = temp_file.name
        
        # Upload to GCS
        blob = bucket.blob(filename)
        blob.upload_from_filename(temp_file_path)
        
        # Make the blob publicly accessible
        blob.make_public()
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        return blob.public_url
        
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        raise

@functions_framework.http
def process_photo(request):
    """Cloud Function to process photos with Gemini API and add frames"""
    
    # Set CORS headers
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }
    
    try:
        # Check if it's a POST request
        if request.method != 'POST':
            return (json.dumps({'success': False, 'error': 'Only POST method is allowed'}), 405, headers)
        
        # Check if photo file is present
        if 'photo' not in request.files:
            return (json.dumps({'success': False, 'error': 'No photo file provided'}), 400, headers)
        
        photo_file = request.files['photo']
        
        # Validate file type
        if not photo_file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return (json.dumps({'success': False, 'error': 'Invalid file type. Only JPG, JPEG, and PNG are allowed'}), 400, headers)
        
        # Open and process the image
        image = Image.open(photo_file)
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Analyze image with Gemini for software issues
        analysis_result = analyze_image_with_gemini(image)
        
        # Determine which frame to use based on analysis
        if analysis_result == "yes":
            print("Software related issue detected")
            frame_path = "yes.png"
            frame_type = "yes"
        else:
            print("No software related issue detected")
            frame_path = "no.png"
            frame_type = "no"
        
        # Create frame around the image
        framed_image = create_framed_image(image, frame_path)
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = f"framed_photos/{timestamp}_{unique_id}_{frame_type}.webp"
        
        # Upload to Google Cloud Storage
        image_url = upload_to_gcs(framed_image, filename)
        
        # Return success response
        response_data = {
            'success': True,
            'imageUrl': image_url,
            'frameStyle': frame_type,
            'analysisResult': analysis_result,
            'message': f'Photo processed successfully with {frame_type} frame'
        }
        
        return (json.dumps(response_data), 200, headers)
        
    except Exception as e:
        print(f"Error processing photo: {e}")
        error_response = {
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }
        return (json.dumps(error_response), 500, headers)
