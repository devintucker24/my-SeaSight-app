#!/usr/bin/env python3
"""
🚢 Maritime Route Optimizer - Web Application Launcher
===============================================

Quick launcher for the Maritime Route Optimizer web application.

Usage:
    python run_web_app.py

This will start the FastAPI web server with the full maritime route optimization platform.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import jinja2
        import folium
        print("✅ All web dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def main():
    """Main launcher function"""
    print("🚢 Maritime Route Optimizer - Web Application")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("web_app.py").exists():
        print("❌ web_app.py not found in current directory")
        print("Please run this script from the project root directory")
        sys.exit(1)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    print("🌊 Starting web application...")
    print("📡 Server will be available at: http://localhost:8000")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 50)

    try:
        # Run the web application
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "web_app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
            "--log-level", "info"
        ], check=True)

    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Server failed to start: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
