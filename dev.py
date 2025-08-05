#!/usr/bin/env python3
"""
Development server with hot reloading for WhatTheFork app.
Automatically restarts the app when Python files change.
"""

import subprocess
import sys
from pathlib import Path
from watchfiles import watch

def run_app():
    """Run the main application"""
    return subprocess.Popen([sys.executable, "WTF.py"])

def main():
    """Main development server with file watching"""
    print("🔥 Starting WhatTheFork in development mode with hot reloading...")
    print("📁 Watching for changes in: *.py files")
    print("🛑 Press Ctrl+C to stop\n")
    
    # Start the app initially
    process = run_app()
    
    try:
        # Watch for changes in Python files
        for changes in watch('.', watch_filter=lambda change, path: path.endswith('.py')):
            print(f"\n🔄 Detected changes:")
            for change_type, file_path in changes:
                print(f"   {change_type.name}: {file_path}")
            
            print("🔄 Restarting app...")
            
            # Kill the current process
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            
            # Start a new process
            process = run_app()
            print("✅ App restarted successfully!\n")
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down development server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()