#!/bin/bash

# Quick Virtual Environment Setup Script
echo "🔧 Setting up Python virtual environment..."

# Create virtual environment
if python3 -m venv venv; then
    echo "✅ Virtual environment created"
else
    echo "❌ Failed to create virtual environment"
    exit 1
fi

# Activate and install dependencies
echo "📦 Installing dependencies..."
if source venv/bin/activate && pip install -r requirements.txt; then
    echo "✅ Dependencies installed successfully"
    echo ""
    echo "🎉 Setup complete!"
    echo ""
    echo "To use the script:"
    echo "1. Activate virtual environment: source venv/bin/activate"
    echo "2. Run the script: python backup_sync.py --test-telegram"
    echo ""
    echo "Or run the full installation: ./install.sh"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi