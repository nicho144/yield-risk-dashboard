#!/bin/bash

# Create necessary directories
mkdir -p .streamlit
mkdir -p cache

# Copy secrets template if secrets.toml doesn't exist
if [ ! -f .streamlit/secrets.toml ]; then
    cp .streamlit/secrets.toml.template .streamlit/secrets.toml
    echo "Created .streamlit/secrets.toml from template. Please update with your API keys."
fi

# Install dependencies
pip install -r requirements.txt

# Create .gitignore
cat > .gitignore << EOL
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
.streamlit/secrets.toml
cache/
*.log
EOL

# Make the script executable
chmod +x deploy.sh

echo "Deployment setup complete. Please:"
echo "1. Update .streamlit/secrets.toml with your API keys"
echo "2. Commit your changes to GitHub"
echo "3. Go to share.streamlit.io and deploy your app" 