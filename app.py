import gradio as gr

def classify_food(image):
    # Simulate image classification
    return "burger"

def get_calories(food):
    calories = {"burger": 295, "salad": 150, "pizza": 266}
    return calories.get(food, 250)

def recommend_diet(calories):
    if calories > 600:
        return "High calorie! Try grilled options next time."
    return "Nice choice for a balanced meal!"

def full_pipeline(image):
    food = classify_food(image)
    cal = get_calories(food)
    advice = recommend_diet(cal)
    return f"Food: {food}\nCalories: {cal}\nAdvice: {advice}"

gr.Interface(fn=full_pipeline,
             inputs=gr.Image(type="pil"),
             outputs="text").launch()