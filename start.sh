#!/bin/bash

echo "========================================"
echo "  Branca de Neve 1.0 - Quick Start"
echo "========================================"
echo ""

# Check for docker
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "Docker found! Starting with Docker Compose..."
    echo ""
    docker-compose up -d
    echo ""
    echo "Services starting..."
    echo "Frontend: http://localhost:3000"
    echo "Backend:  http://localhost:8001"
    echo "API Docs: http://localhost:8001/docs"
    echo ""
    echo "Use 'docker-compose logs -f' to see logs"
    echo "Use 'docker-compose down' to stop"
else
    echo "Docker not found. Please install Docker and Docker Compose."
    echo "Or follow manual setup in SETUP_INDEPENDENTE.md"
    exit 1
fi
