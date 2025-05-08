#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Starting Streamlit Cloud deployment...${NC}"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is not installed${NC}"
    exit 1
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo -e "${YELLOW}Installing streamlit...${NC}"
    pip install streamlit
fi

# Create necessary directories
mkdir -p .streamlit
mkdir -p cache

# Check if .git directory exists
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}Initializing git repository...${NC}"
    git init
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo -e "${YELLOW}Creating .gitignore...${NC}"
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
fi

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Check if changes need to be committed
if git diff --quiet && git diff --cached --quiet; then
    echo -e "${YELLOW}No changes to commit${NC}"
else
    echo -e "${YELLOW}Committing changes...${NC}"
    git add .
    git commit -m "Update for Streamlit Cloud deployment"
fi

# Check if remote exists
if ! git remote | grep -q "origin"; then
    echo -e "${YELLOW}Please add your GitHub repository as remote 'origin'${NC}"
    echo -e "Example: git remote add origin https://github.com/username/repo.git"
    exit 1
fi

# Push to GitHub
echo -e "${YELLOW}Pushing to GitHub...${NC}"
git push origin main

echo -e "${GREEN}Deployment preparation complete!${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Go to https://share.streamlit.io"
echo "2. Sign in with your GitHub account"
echo "3. Click 'New app'"
echo "4. Select your repository"
echo "5. Set the main file path to: streamlite_financial_improved.py"
echo "6. Click 'Deploy'"
echo -e "${GREEN}Your app will be available at: https://share.streamlit.io/your-username/your-repo/main${NC}" 