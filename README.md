# 🍽️ WhatTheFork? - Smart Meal Analysis & Calorie Tracker

An intelligent web app that analyzes food photos using AI and provides comprehensive nutritional information with daily calorie progress tracking.

## ✨ Features

- 📷 **AI-Powered Food Analysis**: Upload food images and get detailed nutritional breakdown
- 📊 **Visual Progress Tracking**: Interactive progress bar showing daily calorie intake vs. goal
- 🎯 **Customizable Goals**: Set your personal daily calorie target (500-5000 calories)
- 📈 **Real-time Updates**: Automatic daily calorie accumulation with smart daily reset
- 🎨 **Modern Interface**: Clean, responsive UI built with Gradio
- 📋 **Detailed Results**: Get calories, fats, proteins, carbs, and raw JSON data

## 🚀 Run the App

### Production Mode
```bash
pip install -r requirements.txt
python WTF.py
```

### 🔥 Development Mode (Hot Reloading)
For development with automatic restarting when files change:

**Option 1: Using the development server (Recommended)**
```bash
pip install -r requirements.txt
python dev.py
```

**Option 2: Windows users can double-click**
```
dev.bat
```

**Option 3: Using external tools**
```bash
# Using watchfiles directly
pip install watchfiles
watchfiles --ignore-paths .git python WTF.py

# Using nodemon (if you have Node.js)
npm install -g nodemon
nodemon --exec python WTF.py --ext py
```

## 🛠️ Development Features

- **🔄 Hot Reloading**: Automatically restarts when `.py` files change
- **📁 File Watching**: Monitors all Python files in the project
- **⚡ Fast Restart**: Quick process restart without manual intervention
- **🖥️ Auto Browser**: Opens browser automatically in development mode
