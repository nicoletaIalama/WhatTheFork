"""
User Profile Modal Panel for WhatTheFork App
Collects user information to calculate personalized daily calorie goals
"""

import gradio as gr
import json
import os
from datetime import datetime


class UserProfile:
    """Handles user profile data and calorie calculations"""
    
    def __init__(self):
        self.profile_file = "user_profile.json"
        self.current_profile = self.load_profile()
    
    def load_profile(self):
        """Load existing user profile from file"""
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def save_profile(self, profile_data):
        """Save user profile to file"""
        try:
            profile_data['last_updated'] = datetime.now().isoformat()
            with open(self.profile_file, 'w') as f:
                json.dump(profile_data, f, indent=2)
            self.current_profile = profile_data
            return True
        except Exception as e:
            print(f"Error saving profile: {e}")
            return False
    
    def calculate_bmr(self, age, gender, height_cm, weight_kg):
        """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation"""
        if gender.lower() == 'male':
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        else:  # female
            bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
        return bmr
    
    def calculate_daily_calories(self, bmr, activity_level):
        """Calculate daily calorie needs based on BMR and activity level"""
        activity_multipliers = {
            'sedentary': 1.2,           # Little/no exercise
            'light': 1.375,             # Light exercise 1-3 days/week
            'moderate': 1.55,           # Moderate exercise 3-5 days/week
            'active': 1.725,            # Hard exercise 6-7 days/week
            'very_active': 1.9          # Very hard exercise, physical job
        }
        
        multiplier = activity_multipliers.get(activity_level, 1.55)
        return int(bmr * multiplier)


def create_profile_modal():
    """Create the user profile modal interface"""
    
    profile_manager = UserProfile()
    
    def submit_profile(name, age, gender, height, weight, activity, goal_type):
        """Process and save the user profile"""
        
        # Validation
        errors = []
        
        if not name or len(name.strip()) < 2:
            errors.append("Please enter a valid name (at least 2 characters)")
        
        if not age or age < 10 or age > 120:
            errors.append("Please enter a valid age (10-120 years)")
        
        if not height or height < 100 or height > 250:
            errors.append("Please enter a valid height (100-250 cm)")
        
        if not weight or weight < 30 or weight > 300:
            errors.append("Please enter a valid weight (30-300 kg)")
        
        if errors:
            error_msg = "❌ **Please fix the following errors:**\n" + "\n".join(f"• {error}" for error in errors)
            return error_msg, 2000
        
        # Calculate BMR and daily calories
        bmr = profile_manager.calculate_bmr(age, gender, height, weight)
        base_calories = profile_manager.calculate_daily_calories(bmr, activity)
        
        # Adjust based on goal
        goal_adjustments = {
            'maintain': 1.0,
            'lose_slow': 0.9,      # 10% deficit
            'lose_fast': 0.8,      # 20% deficit
            'gain_slow': 1.1,      # 10% surplus
            'gain_fast': 1.2       # 20% surplus
        }
        
        final_calories = int(base_calories * goal_adjustments.get(goal_type, 1.0))
        
        # Create profile data
        profile_data = {
            'name': name.strip(),
            'age': age,
            'gender': gender,
            'height_cm': height,
            'weight_kg': weight,
            'activity_level': activity,
            'goal_type': goal_type,
            'bmr': bmr,
            'maintenance_calories': base_calories,
            'target_calories': final_calories
        }
        
        # Save profile
        if profile_manager.save_profile(profile_data):
            success_msg = f"""✅ **Profile Saved Successfully!**

👤 **Your Information:**
• Name: {name}
• Age: {age} years
• Gender: {gender.title()}
• Height: {height} cm
• Weight: {weight} kg
• Activity: {activity.replace('_', ' ').title()}

📊 **Your Calorie Goals:**
• BMR (Base Metabolic Rate): {bmr:,} calories
• Maintenance Calories: {base_calories:,} calories
• Target Daily Calories: **{final_calories:,} calories**

🎯 **Goal**: {goal_type.replace('_', ' ').title()}

Your daily calorie target has been set to **{final_calories:,} calories** based on your profile and goals."""
            
            # Return success message and calories
            return success_msg, final_calories
        else:
            error_msg = "❌ **Error saving profile.** Please try again."
            return error_msg, 2000
    

    
    # Load existing profile data for default values
    existing_profile = profile_manager.current_profile
    default_name = existing_profile.get('name', '') if existing_profile else ''
    default_age = existing_profile.get('age', 25) if existing_profile else 25
    default_gender = existing_profile.get('gender', 'male') if existing_profile else 'male'
    default_height = existing_profile.get('height_cm', 170) if existing_profile else 170
    default_weight = existing_profile.get('weight_kg', 70) if existing_profile else 70
    default_activity = existing_profile.get('activity_level', 'moderate') if existing_profile else 'moderate'
    default_goal = existing_profile.get('goal_type', 'maintain') if existing_profile else 'maintain'
    
    # Create the modal interface
    with gr.Blocks(title="User Profile Setup") as profile_modal:
        gr.Markdown("# 👤 User Profile Setup")
        gr.Markdown("Please enter your information to calculate personalized daily calorie goals.")
        
        with gr.Row():
            with gr.Column():
                # Personal Information
                gr.Markdown("### 📋 Personal Information")
                
                name_input = gr.Textbox(
                    label="👤 Full Name",
                    placeholder="Enter your name",
                    value=default_name,
                    lines=1
                )
                
                age_input = gr.Number(
                    label="🎂 Age",
                    value=default_age,
                    minimum=10,
                    maximum=120,
                    precision=0,
                    interactive=True
                )
                
                gender_input = gr.Radio(
                    label="⚧ Gender",
                    choices=['male', 'female'],
                    value=default_gender,
                    interactive=True
                )
                
                height_input = gr.Number(
                    label="📏 Height (cm)",
                    value=default_height,
                    minimum=100,
                    maximum=250,
                    precision=0,
                    interactive=True
                )
                
                weight_input = gr.Number(
                    label="⚖️ Weight (kg)",
                    value=default_weight,
                    minimum=30,
                    maximum=300,
                    precision=1,
                    interactive=True
                )

                # Activity and Goals
                gr.Markdown("### 🏃 Activity & Goals")
                
                activity_input = gr.Radio(
                    label="🏃‍♂️ Physical Activity Level",
                    choices=[
                        ('sedentary', 'Sedentary (little/no exercise)'),
                        ('light', 'Light (exercise 1-3 days/week)'),
                        ('moderate', 'Moderate (exercise 3-5 days/week)'),
                        ('active', 'Active (exercise 6-7 days/week)'),
                        ('very_active', 'Very Active (intense exercise/physical job)')
                    ],
                    value=default_activity,
                    interactive=True
                )
                
                goal_input = gr.Radio(
                    label="🎯 Your Goal",
                    choices=[
                        ('lose_fast', '🔥 Lose Weight Fast (-20%)'),
                        ('lose_slow', '📉 Lose Weight Slowly (-10%)'),
                        ('maintain', '⚖️ Maintain Current Weight'),
                        ('gain_slow', '📈 Gain Weight Slowly (+10%)'),
                        ('gain_fast', '💪 Gain Weight Fast (+20%)')
                    ],
                    value=default_goal,
                    interactive=True
                )
                
                # Buttons
                save_btn = gr.Button("💾 Save Profile", variant="primary", size="lg")
        
        # Results and feedback
        result_output = gr.Markdown(
            label="Results",
            visible=True
        )
        calculated_calories = gr.Number(
            label="🎯 Your Daily Calorie Target",
            value=existing_profile.get('target_calories', 2000) if existing_profile else 2000,
            interactive=False
        )
        
        # Event handlers
        save_btn.click(
            fn=submit_profile,
            inputs=[name_input, age_input, gender_input, height_input, weight_input, activity_input, goal_input],
            outputs=[result_output, calculated_calories]
        )
    
    return profile_modal


def get_user_daily_calories():
    """Get the user's target daily calories from saved profile"""
    profile_manager = UserProfile()
    profile = profile_manager.current_profile
    return profile.get('target_calories', 2000) if profile else 2000


def get_user_name():
    """Get the user's name from saved profile"""
    profile_manager = UserProfile()
    profile = profile_manager.current_profile
    return profile.get('name', 'User') if profile else 'User'


if __name__ == "__main__":
    # Test the modal interface
    demo = create_profile_modal()
    demo.launch(inbrowser=True)