import gradio as gr
import ollama
import base64
from PIL import Image
from database import create_db_and_tables, save_food, get_all_foods
import io
import time
import json
import re
import os
from datetime import datetime
from user_profile import create_profile_modal, get_user_daily_calories, get_user_name

# Global state for calorie tracking
daily_calories = 0
current_date = datetime.now().date()
daily_goal = get_user_daily_calories()  # Loads from user profile

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
    
     # Use purple theme color by default, red only when over 100%
    if percentage > 100:
        color = "#F44336"  # Red (over goal)
    else:
        color = "#4F46DE"  # Purple theme color
    
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
                         <div style="position: relative; height: 30px; width: 100%;">
                 <div style="background-color: {color}; height: 100%; width: {visual_width}%; border-radius: 6px; transition: all 0.3s ease;"></div>
                 <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; color: #333; font-weight: bold;">
                     {percentage:.1f}%
                 </div>
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
    """Chat function that handles both text and images with calorie tracking and streaming"""
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
                
                # Get comprehensive analysis from image (single call)
                try:
                    initial_response = ollama.generate(
                        model='llava',
                        prompt='''Analyze this food image and provide a comprehensive analysis. Your response should include:

1. A short, descriptive name for the meal (2-4 words max, examples: "Grilled Chicken Salad", "Pepperoni Pizza")
2. A detailed description of what you see in the image
3. Nutritional information in JSON format: {"total_calories": 500, "total_fats_g": 25, "total_proteins_g": 30, "total_carbs_g": 45}
4. Key nutritional highlights and insights

Structure your response clearly with these sections. Be thorough but concise.''',
                        images=[image_base64],
                        options={
                            'temperature': 0.3,
                            'num_predict': 300,   # Longer for comprehensive analysis
                            'num_ctx': 1024,
                            'top_p': 0.8,
                            'repeat_penalty': 1.1
                        }
                    )
                except Exception as ollama_error:
                    ai_response = f"Processing failed: {ollama_error}"
                    user_message = f"{message} [🖼️ Error]" if message.strip() else "[🖼️ Error]"
                    history.append((user_message, ai_response))
                    yield "", history
                    return
                
                initial_analysis = initial_response.get('response', 'No response received from model')
                
                # Extract meal name from the initial analysis
                try:
                    name_response = ollama.generate(
                        model='llama3.2',
                        prompt=f'''Based on this food analysis, extract ONLY the meal name (2-4 words max). Return just the name, nothing else.

Analysis: {initial_analysis}

Examples of good names: "Grilled Chicken Salad", "Pepperoni Pizza", "Beef Burger", "Caesar Salad"''',
                        options={
                            'temperature': 0.1,
                            'num_predict': 10,
                            'num_ctx': 512,
                            'top_p': 0.6,
                            'repeat_penalty': 1.1
                        }
                    )
                    meal_name = name_response.get('response', '').strip()
                    # Clean up the name
                    meal_name = meal_name.replace('"', '').replace("'", "").strip()
                    if not meal_name or len(meal_name) > 50:
                        meal_name = f"Meal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                except Exception as name_error:
                    print(f"⚠️ Error extracting meal name: {name_error}")
                    meal_name = f"Meal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Extract JSON from the initial analysis
                json_response_text = initial_analysis
                
                # Process and validate JSON response
                nutrition_data = None
                meal_calories = 0

                if json_response_text and len(json_response_text.strip()) > 0:
                    try:
                        # Extract JSON from response (in case there's extra text)
                        json_match = re.search(r'\{.*\}', json_response_text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group()
                            # Validate it's proper JSON
                            nutrition_data = json.loads(json_str)

                            try:
                                saved_food = save_food(
                                    name=meal_name,
                                    calories=nutrition_data.get('total_calories', 0),
                                    fats=nutrition_data.get('total_fats_g', 0),
                                    proteins=nutrition_data.get('total_proteins_g', 0),
                                    carbs=nutrition_data.get('total_carbs_g', 0)
                                )
                                print(f"✅ Saved '{meal_name}' to database")
                            except Exception as db_error:
                                print(f"❌ Database error: {db_error}")
                            
                            # Extract calories and update daily total
                            meal_calories = nutrition_data.get('total_calories', 0)
                            daily_calories += meal_calories
                            
                            # Log JSON data to terminal
                            print(f"\n🍽️ Nutrition Data (JSON): {json.dumps(nutrition_data, indent=2)}")

                    except json.JSONDecodeError:
                        print(f"\n⚠️ Failed to extract JSON from response: {json_response_text}")

                # Format the user message to show they shared an image
                if message.strip():
                    user_message = f"{message} [🖼️]"
                else:
                    user_message = "[🖼️ Food image]"

                # Add user message immediately
                history.append((user_message, ""))

                # Now generate the final streaming response using the text analysis
                if message.strip():
                    if nutrition_data:
                        description_prompt = f"""I've shared an image of food with you along with this message: "{message}"

Previous analysis: {initial_analysis}

Format your response as:

🍽️ **Meal Name:**
[Provide ONLY a name for the meal using 2-6 words, no description]

📊 **Nutritional Information:**
• 🔥 Calories: {nutrition_data.get('total_calories', 'N/A')}
• 🥑 Fats: {nutrition_data.get('total_fats_g', 'N/A')}g  
• 🥩 Proteins: {nutrition_data.get('total_proteins_g', 'N/A')}g
• 🍞 Carbs: {nutrition_data.get('total_carbs_g', 'N/A')}g

📈 **Daily Progress:**
• Meal added: +{meal_calories} calories
• Total today: {daily_calories} calories  
• Daily goal: {daily_goal} calories

Then provide relevant advice based on the user's message and nutritional analysis. Be conversational and helpful."""
                    else:
                        description_prompt = f"""Based on this food analysis and the user's message "{message}", create a helpful response:

Previous analysis: {initial_analysis}

Format your response as:
🍽️ **Meal Analysis Results**

1. Provide ONLY a name for the meal using 2-6 words, no description.
2. General nutritional insights about the food
3. Relevant advice based on the user's message

Be conversational and helpful."""
                else:
                    if nutrition_data:
                        description_prompt = f"""Based on this food analysis, create a complete meal analysis response:

Previous analysis: {initial_analysis}

Format your response as:

🍽️ **Meal Analysis Results**

Provide ONLY a name for the meal using 2-6 words, no description.

📊 **Nutritional Information:**
• 🔥 Calories: {nutrition_data.get('total_calories', 'N/A')}
• 🥑 Fats: {nutrition_data.get('total_fats_g', 'N/A')}g
• 🥩 Proteins: {nutrition_data.get('total_proteins_g', 'N/A')}g  
• 🍞 Carbs: {nutrition_data.get('total_carbs_g', 'N/A')}g

📈 **Daily Progress:**
• Meal added: +{meal_calories} calories
• Total today: {daily_calories} calories
• Daily goal: {daily_goal} calories

Then provide one helpful insight or tip about the meal. Be conversational and helpful."""
                    else:
                        description_prompt = f"""I've shared an image of food with you. Please provide a meal analysis that includes:

Previous analysis: {initial_analysis}

🍽️ **Meal Name:**
[Provide ONLY a name for the meal using 2-6 words, no description]

[Provide general nutritional insights and one helpful tip. Be conversational and helpful.]"""
                
                # Add user message immediately
                history[-1] = (user_message, "")
                yield "", history

                # Stream the full response using text model (no image needed)
                ai_response = ""
                try:
                    stream = ollama.generate(
                        model='llama3.2',
                        prompt=description_prompt,
                        stream=True,
                        options={
                            'temperature': 0.7,
                            'num_predict': 300,  # Increased for full response
                            'num_ctx': 2048,     # Increased for longer context
                            'top_p': 0.9,
                            'repeat_penalty': 1.1
                        }
                    )

                    for chunk in stream:
                        if chunk.get('response'):
                            ai_response += chunk['response']
                            # Update the last message in history with streaming response
                            history[-1] = (user_message, ai_response)
                            yield "", history

                except Exception as e:
                    ai_response = f"Sorry, I had trouble analyzing the image: {str(e)}"
                    history[-1] = (user_message, ai_response)
                    yield "", history
                    
            except Exception as e:
                ai_response = f"Sorry, I had trouble processing that image: {str(e)}"
                user_message = f"{message} [🖼️ Error]" if message.strip() else "[🖼️ Error]"
                history.append((user_message, ai_response))
                yield "", history
        
        else:
            # Text-only conversation with database-informed responses
            if not message.strip():
                yield "", history
                return
            
            # Query database for user's food history to provide informed responses
            try:
                # Get all foods from database
                all_foods = get_all_foods()
                
                # Format all foods for context
                meals_text = ""
                if all_foods:
                    meals_text = "Complete meal tracking history (all meals user has logged):\n"
                    for food in all_foods:
                        meals_text += f"- {food.name}: {food.calories} calories, {food.proteins}g protein, {food.carbs}g carbs, {food.fats}g fat\n"
                else:
                    meals_text = "Complete meal tracking history: The user has not logged any meals yet (database is empty)."
                
            except Exception as db_error:
                print(f"⚠️ Database query error: {db_error}")
                meals_text = "Unable to retrieve meal history."
            
            # Create informed conversational prompt using database data
            prompt = f"""You are a helpful nutritionist and food expert. I am providing you with the user's complete food tracking data below. The user asked: "{message}"

IMPORTANT: You have full access to their meal history and daily progress. Use this data to provide personalized advice.

Current daily progress:
- Daily calories consumed: {daily_calories}
- Daily calorie goal: {daily_goal}
- Remaining calories: {daily_goal - daily_calories}

{meals_text}

Based on the meal history and daily progress data provided above, give personalized advice about nutrition, healthy eating, meal planning, diet analysis, or fitness. Always reference their actual tracked meals when relevant. Be conversational, informative, and supportive."""

            # Debug: Print what data is being sent to the model
            print(f"\n🔍 Debug - Meals found in database: {len(all_foods) if all_foods else 0}")
            print(f"🔍 Debug - Daily calories: {daily_calories}")
            if all_foods:
                print(f"🔍 Debug - Sample meals: {[food.name for food in all_foods[:3]]}")
            else:
                print("🔍 Debug - No meals in database!")
            print(f"🔍 Debug - Prompt length: {len(prompt)} characters")

            # Add user message immediately
            history.append((message, ""))
            yield "", history
            
            # Stream the text response
            ai_response = ""
            try:
                stream = ollama.generate(
                    model='llama3.2',
                    prompt=prompt,
                    stream=True,
                    options={
                        'temperature': 0.8,
                        'num_predict': 250,  # Slightly longer for more detailed responses
                        'num_ctx': 2048,     # Increased for longer context with database data
                        'top_p': 0.9,
                        'repeat_penalty': 1.1
                    }
                )
                
                for chunk in stream:
                    if chunk.get('response'):
                        ai_response += chunk['response']
                        # Update the last message in history with streaming response
                        history[-1] = (message, ai_response)
                        yield "", history
                        
            except Exception as e:
                ai_response = f"Sorry, I had trouble responding to that: {str(e)}"
                history[-1] = (message, ai_response)
                yield "", history

    except Exception as e:
        error_message = f"Sorry, I encountered an error: {str(e)}"
        if message.strip():
            history.append((message, error_message))
        yield "", history

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
        /* Improved Modal - No Scrolling, Better Flow */
        .modal-overlay {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background-color: rgba(0, 0, 0, 0.8) !important;
            z-index: 9999 !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            padding: 15px !important;
            backdrop-filter: blur(8px) !important;
            animation: fadeIn 0.3s ease-out !important;
        }

        .modal-card {
            background: white !important;
            border-radius: 16px !important;
            max-width: 700px !important;
            width: 90% !important;
            max-height: 90vh !important;
            overflow: hidden !important;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.4) !important;
            animation: modalSlideIn 0.4s ease-out !important;
            position: relative !important;
            display: flex !important;
            flex-direction: column !important;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes modalSlideIn {
            from { opacity: 0; transform: translateY(-30px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .modal-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            padding: 18px 25px 14px 25px !important;
            position: relative !important;
            flex-grow: 0 !important;
            border-radius: 16px 16px 0 0 !important;
        }

        .modal-close-small {
            position: absolute !important;
            top: 10px !important;
            right: 12px !important;
            background: rgba(255, 255, 255, 0.2) !important;
            color: white !important;
            border: none !important;
            border-radius: 50% !important;
            width: 24px !important;
            height: 24px !important;
            cursor: pointer !important;
            font-size: 14px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: all 0.2s ease !important;
            font-weight: bold !important;
        }

        .modal-close-small:hover {
            background: rgba(255, 255, 255, 0.3) !important;
            transform: scale(1.1) !important;
        }

        .modal-body-improved {
            padding: 25px !important;
            flex: 1 !important;
            overflow-y: auto !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 20px !important;
        }

        .form-section-improved {
            background: #f8f9fa !important;
            padding: 18px !important;
            border-radius: 10px !important;
            border: 1px solid #dee2e6 !important;
        }

        .form-grid-improved {
            display: grid !important;
            grid-template-columns: 1fr !important;
            gap: 18px !important;
        }

        @media (max-width: 768px) {
            .form-grid-improved {
                grid-template-columns: 1fr !important;
            }
        }
        /* Ensure all form elements are interactive */
        .modal-body input,
        .modal-body select,
        .modal-body textarea,
        .modal-body button,
        .modal-body label {
            pointer-events: auto !important;
            z-index: 10001 !important;
            position: relative !important;
        }
        """
    ) as demo:
        with gr.Column(elem_classes=["main"]):
            # Header with profile button
            with gr.Row():
                with gr.Column():
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
                lines=1,
                max_lines=1,
                show_label=False,
                submit_btn=True,
                autofocus=True,
                elem_classes=["input-container"]
            )
            
            # Reset button for daily calories
            with gr.Row():
                reset_btn = gr.Button("🔄 Reset Daily Calories", variant="secondary")
                profile_btn = gr.Button("👤 Edit Profile", variant="secondary")
            
            # Modal overlay
            modal_overlay = gr.Column(visible=False, elem_classes=["modal-overlay"])
            with modal_overlay:
                modal_card = gr.Column(elem_classes=["modal-card"])
                with modal_card:
                    
                    # Header with small close button
                    with gr.Column(elem_classes=["modal-header"]):
                        gr.HTML("""
                        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">👤 User Profile Setup</h2>
                        <p style="margin: 4px 0 0 0; opacity: 0.9; font-size: 13px;">Create your personalized nutrition profile</p>
                        """)
                        close_btn = gr.Button("×", elem_classes=["modal-close-small"])
                    
                    # Body with improved form layout
                    with gr.Column(elem_classes=["modal-body-improved"]):
                        
                        # Two-column form grid (no scrolling needed)
                        with gr.Column(elem_classes=["form-grid-improved"]):
                            with gr.Row():
                                # Personal Information Section
                                with gr.Column(elem_classes=["form-section-improved"]):
                                    gr.HTML('<h3 style="color: #495057; margin: 0 0 12px 0; font-size: 15px; border-bottom: 2px solid #667eea; padding-bottom: 6px;">📋 Personal Information</h3>')
                                    
                                    # Your form fields here
                                    name_input = gr.Textbox(label="👤 Name", placeholder="Enter your name")
                                    
                                    with gr.Row():
                                        age_input = gr.Number(label="🎂 Age", value=25, minimum=10, maximum=120)
                                        gender_input = gr.Radio(label="⚧ Gender", choices=['male', 'female'], value='male')
                                    
                                    with gr.Row():
                                        height_input = gr.Number(label="📏 Height (cm)", value=170, minimum=100, maximum=250)
                                        weight_input = gr.Number(label="⚖️ Weight (kg)", value=70, minimum=30, maximum=300)
                                
                                # Activity & Goals Section
                                with gr.Column(elem_classes=["form-section-improved"]):
                                    gr.HTML('<h3 style="color: #495057; margin: 0 0 12px 0; font-size: 15px; border-bottom: 2px solid #667eea; padding-bottom: 6px;">🏃 Activity & Goals</h3>')
                                    
                                    activity_input = gr.Radio(
                                        label="🏃‍♂️ Activity Level",
                                        choices=[('sedentary', 'Sedentary'), ('light', 'Light'), ('moderate', 'Moderate'), ('active', 'Active'), ('very_active', 'Very Active')],
                                        value='moderate'
                                    )
                                    
                                    goal_input = gr.Radio(
                                        label="🎯 Goal",
                                        choices=[('lose_fast', '🔥 Fast Loss'), ('lose_slow', '📉 Slow Loss'), ('maintain', '⚖️ Maintain'), ('gain_slow', '📈 Slow Gain'), ('gain_fast', '💪 Fast Gain')],
                                        value='maintain'
                                    )
                        
                        # Results display
                        result_output = gr.Markdown("", visible=True)
                        
                        # Action buttons
                        with gr.Row(elem_id="form-actions"):
                            save_btn = gr.Button("💾 Save Profile", variant="primary")
                            cancel_btn = gr.Button("Cancel", variant="secondary")

        # Event handler functions (add these inside create_interface())
        def show_profile_modal():
            return gr.update(visible=True)

        def hide_modal():
            return gr.update(visible=False)

        def refresh_goal_from_profile():
            # Update global daily_goal and refresh progress bar
            global daily_goal
            daily_goal = get_user_daily_calories()
            updated_progress = create_progress_bar_html(daily_calories, daily_goal)
            return gr.update(visible=False), updated_progress

        # Connect event handlers (add these at the end of create_interface())
        profile_btn.click(
            fn=show_profile_modal,
            outputs=[modal_overlay]
        )

        close_btn.click(
            fn=hide_modal,
            outputs=[modal_overlay]
        )

        reset_btn.click(
            fn=refresh_goal_from_profile,
            outputs=[modal_overlay, progress_output]
        )

        # Handle multimodal submission with streaming
        def handle_multimodal_submit(multimodal_data, history):
            if multimodal_data is None:
                yield None, history, create_progress_bar_html(daily_calories, daily_goal)
                return
            
            # Extract text and files from multimodal input
            message = multimodal_data.get("text", "") if multimodal_data else ""
            files = multimodal_data.get("files", []) if multimodal_data else []
            
            # Use the first image file if any
            image_path = files[0] if files else None
            
            # Process with streaming chat function
            for result in chat_with_ollama(message, history, image_path):
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
    # Initialize database and tables
    create_db_and_tables()

    # Warm up the model to reduce first-time latency
    warm_up_model()
    
    # Launch the chat interface
    demo = create_interface()
    demo.launch(share=False, server_name="127.0.0.1", server_port=7860)
