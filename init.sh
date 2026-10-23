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
docker compose up -d
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
echo "8. Checking for superuser and test accounts..."
python manage.py shell --settings=config.settings.dev <<EOF
from apps.accounts.models import User, DoctorProfile, PatientProfile

# Create admin
if not User.objects.filter(is_superuser=True).exists():
    print("Creating superuser...")
    User.objects.create_superuser(
        username='admin',
        email='admin@medconsult.com',
        password='admin123',
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    print("✓ Superuser created (admin / admin@medconsult.com / admin123)")
else:
    print("✓ Superuser already exists")

# Create test doctor
if not User.objects.filter(username='testdoctor').exists():
    print("Creating test doctor...")
    doctor_user = User.objects.create_user(
        username='testdoctor',
        email='doctor@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Doctor',
        role='doctor'
    )
    DoctorProfile.objects.create(
        user=doctor_user,
        specialization='General Practice',
        medical_license_number='TEST123456',
        years_of_experience=5,
        consultation_fee=100.00,
        verification_status='verified'
    )
    print("✓ Test doctor created (testdoctor / doctor@test.com / testpass123)")
else:
    print("✓ Test doctor already exists")

# Create test patient
if not User.objects.filter(username='testpatient').exists():
    print("Creating test patient...")
    patient_user = User.objects.create_user(
        username='testpatient',
        email='patient@test.com',
        password='testpass123',
        first_name='Test',
        last_name='Patient',
        role='patient'
    )
    PatientProfile.objects.create(user=patient_user)
    print("✓ Test patient created (testpatient / patient@test.com / testpass123)")
else:
    print("✓ Test patient already exists")
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
echo "3. Login to Django Admin: http://127.0.0.1:8000/admin"
echo "   Username: admin"
echo "   Email: admin@medconsult.com"
echo "   Password: admin123"
echo ""
echo "4. Access Admin Panel: http://127.0.0.1:8000/internal/"
echo "   (Dashboard, Users, Doctors, Appointments, Financial, Audit)"
echo ""
echo "==================================="
