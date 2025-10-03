#!/usr/bin/env python3
"""
Installation script for PDF processing dependencies
Run this script to install all required packages for PDF OCR functionality
"""

import subprocess
import sys
import os

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    """Main installation function"""
    print("🔧 Installing PDF processing dependencies...")
    print("=" * 50)
    
    # List of packages to install
    packages = [
        "PyPDF2>=3.0.0",
        "pdfplumber>=0.9.0", 
        "pytesseract>=0.3.10",
        "Pillow>=10.0.0",
        "pdf2image>=1.16.0"
    ]
    
    success_count = 0
    total_count = len(packages)
    
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print("=" * 50)
    print(f"📊 Installation Summary: {success_count}/{total_count} packages installed successfully")
    
    if success_count == total_count:
        print("🎉 All PDF processing dependencies installed successfully!")
        print("\n📋 Next Steps:")
        print("1. Install Tesseract OCR on your system:")
        print("   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        print("   - Linux: sudo apt-get install tesseract-ocr")
        print("   - macOS: brew install tesseract")
        print("2. Restart your application to use PDF OCR features")
    else:
        print("⚠️ Some packages failed to install. Please check the errors above.")
        print("You may need to install Tesseract OCR separately for full functionality.")

if __name__ == "__main__":
    main()
