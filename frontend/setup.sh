# Create this as frontend/setup.sh
#!/bin/bash

echo "Setting up LMS Frontend..."

# Create public directory if it doesn't exist
mkdir -p public

# Create simple favicon if it doesn't exist
if [ ! -f "public/favicon.ico" ]; then
    echo "Creating placeholder favicon..."
    # You can download a proper favicon later
    touch public/favicon.ico
fi

# Create placeholder logos
if [ ! -f "public/logo192.png" ]; then
    echo "Creating placeholder logo192.png..."
    touch public/logo192.png
fi

if [ ! -f "public/logo512.png" ]; then
    echo "Creating placeholder logo512.png..."
    touch public/logo512.png
fi

echo "Setup complete! You can now run 'npm start'"