#!/bin/bash

# MedConsult Quick Start Script

echo "==================================="
echo "MedConsult Quick Start"
echo "==================================="
echo ""

# Check if Docker is running
echo "1. Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi
echo "✓ Docker is running"
echo ""

# Start Docker services
echo "2. Starting PostgreSQL and Redis..."
docker-compose up -d
sleep 3
echo "✓ Database services started"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "3. Creating Python virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "3. Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "4. Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install dependencies
echo "5. Installing Python dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "6. Creating .env file..."
    cp .env.example .env
    echo "✓ Environment file created"
else
    echo "6. .env file already exists"
fi
echo ""

# Run migrations
echo "7. Running database migrations..."
python manage.py migrate --settings=config.settings.dev
echo "✓ Migrations complete"
echo ""

# Check if superuser exists
echo "8. Checking for superuser..."
python manage.py shell --settings=config.settings.dev <<EOF
from apps.accounts.models import User
if not User.objects.filter(is_superuser=True).exists():
    print("Creating superuser...")
    User.objects.create_superuser(
        email='admin@medconsult.com',
        password='admin123',
        first_name='Admin',
        last_name='User'
    )
    print("✓ Superuser created (admin@medconsult.com / admin123)")
else:
    print("✓ Superuser already exists")
EOF
echo ""

echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Start the development server:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver --settings=config.settings.dev"
echo ""
echo "2. Visit http://127.0.0.1:8000"
echo ""
echo "3. Login to admin: http://127.0.0.1:8000/admin"
echo "   Email: admin@medconsult.com"
echo "   Password: admin123"
echo ""
echo "==================================="
