#!/usr/bin/env python3
"""Check available Gemini models"""

import os
import google.generativeai as genai

# Configure with API key
api_key = "AIzaSyAnmI0sWrLlV5_UXVBBoyHkU2DvBdLlTjs"
genai.configure(api_key=api_key)

print("Checking available Gemini models...\n")

try:
    models = genai.list_models()
    print("Available models for generateContent:")
    for model in models:
        if 'generateContent' in model.supported_generation_methods:
            print(f"  ✅ {model.name}")
            print(f"      Display Name: {model.display_name}")
            print(f"      Description: {model.description}")
            print()
except Exception as e:
    print(f"Error listing models: {e}")

