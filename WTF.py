import gradio as gr
import ollama
import base64
from PIL import Image
from database import create_db_and_tables
import io
import time
import json
import re
from datetime import datetime

# Global state for calorie tracking
daily_calories = 0
current_date = datetime.now().date()

def reset_daily_calories_if_new_day():
    """Reset daily calories if it's a new day"""
    global daily_calories, current_date
    today = datetime.now().date()
    if today != current_date:
        daily_calories = 0
        current_date = today

def create_progress_bar_html(current_calories, daily_goal):
    """Create an HTML progress bar for calorie tracking"""
    if daily_goal <= 0:
        percentage = 0
    else:
        percentage = (current_calories / daily_goal) * 100
    
    # Determine color based on progress (allow over 100%)
    if percentage < 50:
        color = "#4CAF50"  # Green
    elif percentage < 80:
        color = "#FF9800"  # Orange
    elif percentage <= 100:
        color = "#2196F3"  # Blue
    else:
        color = "#F44336"  # Red (over goal)
    
    # Cap the visual width at 100% but show the actual percentage
    visual_width = min(percentage, 100)
    
    # Different messages based on progress
    if percentage >= 100:
        if percentage > 120:
            status_message = f"⚠️ Over goal by {current_calories - daily_goal:.0f} calories!"
        else:
            status_message = "🎉 Great job! You've reached your goal!"
    else:
        status_message = f"💪 {daily_goal - current_calories:.0f} calories remaining"
    
    progress_html = f"""
    <div style="margin: 20px 0;">
        <h3 style="color: #333; margin-bottom: 10px;">📊 Daily Calorie Progress</h3>
        <div style="background-color: #f0f0f0; border-radius: 10px; padding: 4px; width: 100%; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);">
            <div style="background-color: {color}; height: 30px; width: {visual_width}%; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; transition: all 0.3s ease;">
                {percentage:.1f}%
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 14px; color: #666;">
            <span>🔥 {current_calories:.0f} calories consumed</span>
            <span>🎯 Goal: {daily_goal:.0f} calories</span>
        </div>
        <div style="text-align: center; margin-top: 5px; font-size: 13px; color: #888;">
            {status_message}
        </div>
    </div>
    """
    return progress_html

def warm_up_model():
    """Pre-warm the LLaVA model to reduce first-time latency"""
    try:
        ollama.generate(model='llava', prompt='Hello', images=[])
    except Exception as e:
        pass

def analyze_nutrition(image_path, daily_goal):
    global daily_calories
    
    if image_path is None:
        return "Please upload an image.", ""
    
    if daily_goal is None or daily_goal <= 0:
        return "Please set a valid daily calorie goal.", ""
    
    # Reset calories if it's a new day
    reset_daily_calories_if_new_day()

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
                    
                    # Extract calories and update daily total
                    meal_calories = nutrition_data.get('total_calories', 0)
                    daily_calories += meal_calories
                    
                    # Format nutritional information for display
                    formatted_output = f"""
🍽️ **Meal Analysis Results**

📊 **Nutritional Information:**
• 🔥 Calories: {nutrition_data.get('total_calories', 'N/A')}
• 🥑 Fats: {nutrition_data.get('total_fats_g', 'N/A')}g
• 🥩 Proteins: {nutrition_data.get('total_proteins_g', 'N/A')}g
• 🍞 Carbs: {nutrition_data.get('total_carbs_g', 'N/A')}g

📈 **Daily Progress:**
• Meal added: +{meal_calories} calories
• Total today: {daily_calories} calories
• Daily goal: {daily_goal} calories

**Raw JSON:**
```json
{json.dumps(nutrition_data, indent=2)}
```
                    """
                    
                    # Create progress bar
                    progress_bar = create_progress_bar_html(daily_calories, daily_goal)
                    
                    return formatted_output, progress_bar
                else:
                    # If no JSON found, return raw response
                    progress_bar = create_progress_bar_html(daily_calories, daily_goal)
                    return full_response, progress_bar
                    
            except json.JSONDecodeError:
                # If JSON parsing fails, return the raw response
                progress_bar = create_progress_bar_html(daily_calories, daily_goal)
                return f"Raw response (JSON parsing failed): {full_response}", progress_bar
        else:
            progress_bar = create_progress_bar_html(daily_calories, daily_goal)
            return "No response received or response was empty", progress_bar
        
    except Exception as e:
        progress_bar = create_progress_bar_html(daily_calories, daily_goal)
        return f"Error: {str(e)}", progress_bar

# Function to reset daily calories manually
def reset_calories():
    global daily_calories
    daily_calories = 0
    return create_progress_bar_html(daily_calories, 2000)  # Default goal for display

# Build Gradio UI with custom layout
with gr.Blocks(title="WhatTheFork? - Calorie Tracker", theme=gr.themes.Soft()) as iface:
    gr.Markdown("# 🍽️ WhatTheFork? - Smart Meal Analysis & Calorie Tracker")
    gr.Markdown("Upload an image of your meal to get nutritional information and track your daily calorie progress!")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Input section
            gr.Markdown("### 📤 Upload & Settings")
            food_image = gr.Image(type="filepath", label="📷 Upload a food image")
            daily_goal = gr.Number(
                label="🎯 Daily Calorie Goal", 
                value=2000, 
                minimum=500, 
                maximum=5000,
                info="Set your target daily calorie intake"
            )
            
            with gr.Row():
                analyze_btn = gr.Button("🔍 Analyze Meal", variant="primary", size="lg")
                reset_btn = gr.Button("🔄 Reset Daily Count", variant="secondary")
        
        with gr.Column(scale=2):
            # Output section
            gr.Markdown("### 📊 Results")
            nutrition_output = gr.Textbox(
                label="📋 Nutritional Analysis", 
                lines=12, 
                max_lines=20, 
                show_copy_button=True,
                placeholder="Upload a food image and click 'Analyze Meal' to see results..."
            )
            progress_output = gr.HTML(
                label="📈 Daily Progress",
                value=create_progress_bar_html(0, 2000)
            )
    
    # Event handlers
    analyze_btn.click(
        fn=analyze_nutrition,
        inputs=[food_image, daily_goal],
        outputs=[nutrition_output, progress_output]
    )
    
    reset_btn.click(
        fn=reset_calories,
        outputs=progress_output
    )

if __name__ == "__main__":
    # Warm up the model to reduce first-time latency
    warm_up_model()
    # Launch with browser auto-open
    iface.launch(share=True, inbrowser=True)
