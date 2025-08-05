import gradio as gr
import ollama
import base64
from PIL import Image
from database import create_db_and_tables
import io
import time
import json
import re

def warm_up_model():
    """Pre-warm the LLaVA model to reduce first-time latency"""
    try:
        ollama.generate(model='llava', prompt='Hello', images=[])
    except Exception as e:
        pass

def analyze_nutrition(image_path):
    if image_path is None:
        return "Please upload an image."

    try:
        start_time = time.time()
        
        # Open and potentially resize the image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for JPEG compatibility)
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Check if image is larger than 448x448
            width, height = img.size
            max_size = 448
            
            if width > max_size or height > max_size:
                # Calculate new size maintaining aspect ratio
                if width > height:
                    new_width = max_size
                    new_height = int((height * max_size) / width)
                else:
                    new_height = max_size
                    new_width = int((width * max_size) / height)
                
                # Resize the image with faster method
                img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
            
            # Convert to bytes with compression
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=85, optimize=True)
            image_bytes = img_byte_arr.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Use ollama-python to generate response with timeout
        ollama_start = time.time()
        
        try:
            response = ollama.generate(
                model='llava',
                prompt='Analyze this food image and provide nutritional information. Respond ONLY with valid JSON in this exact format: {"total_calories": 500, "total_fats_g": 25, "total_proteins_g": 30, "total_carbs_g": 45}. Estimate the total nutritional values for all food items visible in the image.',
                images=[image_base64],
                options={
                    'temperature': 0.1,   # Very consistent for JSON format
                    'num_predict': 100,   # Short for JSON response
                    'num_ctx': 512,       # Minimal context
                    'top_p': 0.6,         # Focused
                    'repeat_penalty': 1.1  # Avoid repetition
                }
            )
        except Exception as ollama_error:
            return f"Processing failed: {ollama_error}"
        
        full_response = response.get('response', 'No response received from model')
        
        # Process and validate JSON response
        if full_response and len(full_response.strip()) > 0:
            try:
                # Extract JSON from response (in case there's extra text)
                json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    # Validate it's proper JSON
                    nutrition_data = json.loads(json_str)
                    
                    # Format for display
                    formatted_output = json.dumps(nutrition_data, indent=2)
                    return formatted_output
                else:
                    # If no JSON found, return raw response
                    return full_response
                    
            except json.JSONDecodeError:
                # If JSON parsing fails, return the raw response
                return f"Raw response (JSON parsing failed): {full_response}"
        else:
            return "No response received or response was empty"
        
    except Exception as e:
        return f"Error: {str(e)}"

create_db_and_tables()

# Build Gradio UI
iface = gr.Interface(
    fn=analyze_nutrition,
    inputs=gr.Image(type="filepath", label="Upload a food image"),
    outputs=gr.Textbox(label="Nutritional Information (JSON)", lines=15, max_lines=20, show_copy_button=True),
    title="WhatTheFork? - Let me help you analyze your meal",
    description="Upload an image of your meal and get nutritional information in JSON format (calories, fats, proteins, carbs).",
)

if __name__ == "__main__":
    # Warm up the model to reduce first-time latency
    warm_up_model()
    iface.launch()
