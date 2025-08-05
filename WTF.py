import gradio as gr
import ollama
import base64
from PIL import Image
import io
import time
import json
import re
import os
from datetime import datetime

# Global state for calorie tracking
daily_calories = 0
current_date = datetime.now().date()
daily_goal = 2000  # Default daily goal

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

def chat_with_ollama(message: str, history, image_path=None):
    """Chat function that handles both text and images with calorie tracking"""
    global daily_calories, daily_goal
    
    # Reset calories if it's a new day
    reset_daily_calories_if_new_day()
    
    try:
        if image_path and os.path.exists(image_path):
            # Process the image for nutrition analysis
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
                    ai_response = f"Processing failed: {ollama_error}"
                    user_message = f"{message} [🖼️ Error]" if message.strip() else "[🖼️ Error]"
                    history.append((user_message, ai_response))
                    return "", history
                
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
                            formatted_output = f"""🍽️ **Meal Analysis Results**

📊 **Nutritional Information:**
• 🔥 Calories: {nutrition_data.get('total_calories', 'N/A')}
• 🥑 Fats: {nutrition_data.get('total_fats_g', 'N/A')}g
• 🥩 Proteins: {nutrition_data.get('total_proteins_g', 'N/A')}g
• 🍞 Carbs: {nutrition_data.get('total_carbs_g', 'N/A')}g

📈 **Daily Progress:**
• Meal added: +{meal_calories} calories
• Total today: {daily_calories} calories
• Daily goal: {daily_goal} calories

**Raw JSON for database:**
```json
{json.dumps(nutrition_data, indent=2)}
```"""
                            
                            ai_response = formatted_output
                        else:
                            # If no JSON found, return raw response
                            ai_response = full_response
                            
                    except json.JSONDecodeError:
                        # If JSON parsing fails, return the raw response
                        ai_response = f"Raw response (JSON parsing failed): {full_response}"
                else:
                    ai_response = "No response received or response was empty"
                
                # Format the user message to show they shared an image
                if message.strip():
                    user_message = f"{message} [🖼️]"
                else:
                    user_message = "[🖼️ Food image]"
                    
            except Exception as e:
                ai_response = f"Sorry, I had trouble processing that image: {str(e)}"
                user_message = f"{message} [🖼️ Error]" if message.strip() else "[🖼️ Error]"
        
        else:
            # Text-only conversation
            if not message.strip():
                return "", history
            
            # Create conversational prompt for nutrition questions
            prompt = f"""You are a helpful nutritionist and food expert. The user asked: "{message}"

Provide helpful advice about nutrition, healthy eating, meal planning, or calorie management. Be conversational and informative."""

            # Call Ollama for text conversation
            response = ollama.generate(
                model='llama3.2',
                prompt=prompt,
                options={
                    'temperature': 0.8,
                    'num_predict': 200,
                    'num_ctx': 1024,
                    'top_p': 0.9,
                    'repeat_penalty': 1.1
                }
            )
            
            ai_response = response.get('response', 'Sorry, I had trouble responding to that.')
            user_message = message
        
        # Update history
        history.append((user_message, ai_response))
        
        return "", history
        
    except Exception as e:
        error_message = f"Sorry, I encountered an error: {str(e)}"
        if message.strip():
            history.append((message, error_message))
        return "", history

# Function to reset daily calories manually
def reset_calories():
    global daily_calories
    daily_calories = 0
    return create_progress_bar_html(daily_calories, daily_goal)

# Create the chat interface with calorie tracking
def create_interface():
    with gr.Blocks(
        title="WhatTheFork? - Food & Nutrition Chat", 
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
        }
        .main {
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
        }
        .contain {
            height: 100% !important;
            max-height: 100% !important;
            overflow: hidden !important;
        }
        """
    ) as demo:
        with gr.Column(elem_classes=["main"]):
            gr.Markdown(
                """
                # 🍽️ WhatTheFork? - Your Food & Nutrition Chat Assistant
                
                Chat with me about food and nutrition! Upload food images to track calories and get nutritional analysis.
                """,
                elem_classes=["header"]
            )
            
            # Daily progress bar at the top
            progress_output = gr.HTML(
                value=create_progress_bar_html(daily_calories, daily_goal),
                elem_classes=["progress-bar"]
            )
            
            chatbot = gr.Chatbot(
                label="Chat with your nutrition assistant",
                height="50vh",
                show_copy_button=True,
                bubble_full_width=False,
                container=True,
                elem_classes=["chatbot-container"]
            )
            
            # Single multimodal input that handles both text and images
            multimodal_input = gr.MultimodalTextbox(
                placeholder="Type your message or drag and drop a food image here...",
                file_types=["image"],
                lines=3,
                max_lines=6,
                show_label=False,
                submit_btn=True,
                elem_classes=["input-container"]
            )
            
            # Reset button for daily calories
            with gr.Row():
                reset_btn = gr.Button("🔄 Reset Daily Calories", variant="secondary", size="sm")
        
        # Handle multimodal submission
        def handle_multimodal_submit(multimodal_data, history):
            if multimodal_data is None:
                yield None, history, create_progress_bar_html(daily_calories, daily_goal)
                return
            
            # Extract text and files from multimodal input
            message = multimodal_data.get("text", "") if multimodal_data else ""
            files = multimodal_data.get("files", []) if multimodal_data else []
            
            # Use the first image file if any
            image_path = files[0] if files else None
            
            # Process with chat function
            result = chat_with_ollama(message, history, image_path)
            
            # Update progress bar after potential calorie addition
            updated_progress = create_progress_bar_html(daily_calories, daily_goal)
            
            yield None, result[1], updated_progress
        
        # Handle reset button
        def handle_reset():
            updated_progress = reset_calories()
            return updated_progress
        
        # Event handlers
        multimodal_input.submit(
            handle_multimodal_submit,
            inputs=[multimodal_input, chatbot],
            outputs=[multimodal_input, chatbot, progress_output]
        )
        
        reset_btn.click(
            handle_reset,
            outputs=[progress_output]
        )
    
    return demo

if __name__ == "__main__":
    # Warm up the model to reduce first-time latency
    warm_up_model()
    
    # Launch the chat interface
    demo = create_interface()
    demo.launch(share=False, server_name="0.0.0.0", server_port=7860)
