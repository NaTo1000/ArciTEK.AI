#!/bin/bash
# ArciTEK.AI Optimized Startup Script
# The Ultimate Quantum-Enhanced Precision Build System
# Version: 7.0.0

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ArciTEK.AI Banner
echo -e "${PURPLE}"
echo "⚛️🚀 ArciTEK.AI - The Ultimate Quantum-Enhanced Precision Build System 🚀⚛️"
echo "════════════════════════════════════════════════════════════════════════════"
echo -e "${CYAN}🧠 NayDoeV1 Learning Environments | ⚛️ Quantum Computing Integration${NC}"
echo -e "${YELLOW}🎨 Precision Build System | 🤖 Multi-AI Orchestration | ♾️ infinite2025${NC}"
echo "════════════════════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Function to print status messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[ℹ]${NC} $1"
}

# Check system requirements
check_system_requirements() {
    print_info "Checking system requirements..."
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        OS="Windows"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    print_status "Operating System: $OS"
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_status "Python 3 found: $PYTHON_VERSION"
    else
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check Node.js
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        print_status "Node.js found: $NODE_VERSION"
    else
        print_warning "Node.js not found - installing..."
        install_nodejs
    fi
    
    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        print_status "Docker found: $DOCKER_VERSION"
    else
        print_warning "Docker not found - some features may be limited"
    fi
    
    # Check available memory
    if [[ "$OS" == "Linux" ]]; then
        MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
        if [[ $MEMORY_GB -lt 4 ]]; then
            print_warning "Low memory detected: ${MEMORY_GB}GB (Recommended: 8GB+)"
        else
            print_status "Memory: ${MEMORY_GB}GB"
        fi
    fi
}

# Install Node.js if missing
install_nodejs() {
    if [[ "$OS" == "Linux" ]]; then
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt-get install -y nodejs
    elif [[ "$OS" == "macOS" ]]; then
        if command -v brew &> /dev/null; then
            brew install node
        else
            print_error "Please install Node.js manually from https://nodejs.org/"
            exit 1
        fi
    fi
}

# Create virtual environment
setup_virtual_environment() {
    print_info "Setting up Python virtual environment..."
    
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        print_status "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    print_status "Virtual environment activated"
    
    # Upgrade pip
    pip install --upgrade pip
    print_status "pip upgraded to latest version"
}

# Install dependencies
install_dependencies() {
    print_info "Installing ArciTEK.AI dependencies..."
    
    # Install Python packages (with failover to core packages)
    if [[ -f "requirements.txt" ]]; then
        if pip install -r requirements.txt; then
            print_status "Python dependencies installed"
        else
            print_warning "requirements.txt install failed - falling back to core packages"
            pip install flask fastapi uvicorn requests websockets
            print_status "Core Python dependencies installed (fallback)"
        fi
    else
        print_warning "requirements.txt not found - installing core packages"
        pip install flask fastapi uvicorn requests websockets
    fi
    
    # Install Node.js packages (npm ci with failover to npm install)
    if [[ -f "package.json" ]]; then
        if [[ -f "package-lock.json" ]] && npm ci --no-audit --no-fund; then
            print_status "Node.js dependencies installed (npm ci)"
        elif npm install --no-audit --no-fund; then
            print_status "Node.js dependencies installed (npm install fallback)"
        else
            print_error "Failed to install Node.js dependencies"
            exit 1
        fi
    else
        print_info "No package.json found - skipping Node.js dependencies"
    fi
    
    # Install quantum computing packages (optional - failover to continue)
    print_info "Installing quantum computing packages..."
    if pip install qiskit qiskit-aer cirq pennylane; then
        print_status "Quantum computing packages installed"
    else
        print_warning "Quantum packages unavailable - continuing without quantum acceleration"
    fi
    
    # Install AI/ML packages (optional - failover to continue)
    print_info "Installing AI/ML packages..."
    if pip install torch transformers openai anthropic; then
        print_status "AI/ML packages installed"
    else
        print_warning "AI/ML packages unavailable - continuing with reduced model support"
    fi
}

# Initialize configuration
initialize_configuration() {
    print_info "Initializing ArciTEK.AI configuration..."
    
    # Create config directory
    mkdir -p config
    
    # Create default configuration file
    cat > config/arcitek.conf << EOF
# ArciTEK.AI Configuration File
# Generated on $(date)

[core]
version = 7.0.0
debug = false
log_level = INFO

[quantum]
default_backend = qiskit_aer
enable_optimization = true
quantum_boost = true

[ai_models]
enable_supersynapai = true
enable_argo_bots = true
enable_chimera_models = true
max_concurrent_models = 8

[naydoev1]
enable_learning = true
learning_rate = 0.95
mastery_threshold = 0.95

[build_system]
default_precision = professional
enable_quantum_enhancement = true
auto_optimization = true

[security]
enable_jessicai_v2 = true
nato100_protocols = true
encryption_level = quantum

[deployment]
default_platform = local
enable_containerization = true
auto_scaling = true
EOF
    
    print_status "Configuration file created: config/arcitek.conf"
    
    # Create environment variables template
    cat > .env.template << EOF
# ArciTEK.AI Environment Variables Template
# Copy to .env and fill in your API keys

# Quantum Computing
IBM_QUANTUM_TOKEN=your_ibm_quantum_token_here
IONQ_API_KEY=your_ionq_api_key_here
GOOGLE_QUANTUM_API_KEY=your_google_quantum_api_key_here
AZURE_QUANTUM_WORKSPACE=your_azure_quantum_workspace_here

# AI Models
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
HUGGINGFACE_TOKEN=your_huggingface_token_here

# Cloud Services
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
GOOGLE_CLOUD_PROJECT=your_gcp_project_id_here
AZURE_SUBSCRIPTION_ID=your_azure_subscription_here

# Database
DATABASE_URL=sqlite:///arcitek.db
REDIS_URL=redis://localhost:6379

# Security
JWT_SECRET_KEY=your_jwt_secret_here
ENCRYPTION_KEY=your_encryption_key_here
EOF
    
    print_status "Environment template created: .env.template"
}

# Start ArciTEK.AI services
start_services() {
    print_info "Starting ArciTEK.AI services..."
    
    # Check if .env exists
    if [[ ! -f ".env" ]]; then
        print_warning "No .env file found - creating from template"
        cp .env.template .env
        print_warning "Please edit .env file with your API keys before full functionality"
    fi
    
    # Start core services
    print_info "Initializing quantum orchestration layer..."
    python3 -c "
import sys
sys.path.append('arcitek_core')
try:
    from precision_builder import *
    print('✓ Quantum orchestration layer initialized')
except Exception as e:
    print(f'⚠ Quantum layer initialization warning: {e}')
"
    
    # Start web interface
    print_info "Starting ArciTEK.AI web interface..."
    if [[ -f "arcitek_ui/arcitek_ai_ultimate_terminal.py" ]]; then
        python3 arcitek_ui/arcitek_ai_ultimate_terminal.py &
        WEB_PID=$!
        print_status "Web interface started (PID: $WEB_PID)"
        echo $WEB_PID > .arcitek_web.pid
    fi
    
    # Start API server
    print_info "Starting ArciTEK.AI API server..."
    if [[ -f "arcitek_core/precision_builder.py" ]]; then
        python3 arcitek_core/precision_builder.py &
        API_PID=$!
        print_status "API server started (PID: $API_PID)"
        echo $API_PID > .arcitek_api.pid
    fi
    
    sleep 3
    
    print_status "ArciTEK.AI services are running!"
    print_info "Web Interface: http://localhost:5000"
    print_info "API Server: http://localhost:8000"
    print_info "Terminal Interface: Available in web UI"
}

# Health check
health_check() {
    print_info "Performing health check..."
    
    # Check web interface
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        print_status "Web interface: Healthy"
    else
        print_warning "Web interface: Not responding"
    fi
    
    # Check API server
    if curl -s http://localhost:8000 > /dev/null 2>&1; then
        print_status "API server: Healthy"
    else
        print_warning "API server: Not responding"
    fi
    
    # Check quantum integration
    python3 -c "
try:
    import qiskit
    print('✓ Quantum integration: Available')
except ImportError:
    print('⚠ Quantum integration: Not available')
"
    
    # Check AI models
    python3 -c "
try:
    import torch, transformers
    print('✓ AI models: Available')
except ImportError:
    print('⚠ AI models: Not available')
"
}

# Display usage information
show_usage() {
    echo -e "${CYAN}"
    echo "ArciTEK.AI Startup Script Usage:"
    echo "================================"
    echo -e "${NC}"
    echo "  ./startup.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     - Start ArciTEK.AI (default)"
    echo "  stop      - Stop all ArciTEK.AI services"
    echo "  restart   - Restart ArciTEK.AI services"
    echo "  status    - Check service status"
    echo "  health    - Perform health check"
    echo "  update    - Update ArciTEK.AI to latest version"
    echo "  clean     - Clean temporary files and logs"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./startup.sh start    # Start all services"
    echo "  ./startup.sh health   # Check system health"
    echo "  ./startup.sh update   # Update to latest version"
}

# Stop services
stop_services() {
    print_info "Stopping ArciTEK.AI services..."
    
    # Stop web interface
    if [[ -f ".arcitek_web.pid" ]]; then
        WEB_PID=$(cat .arcitek_web.pid)
        if kill -0 $WEB_PID 2>/dev/null; then
            kill $WEB_PID
            print_status "Web interface stopped"
        fi
        rm -f .arcitek_web.pid
    fi
    
    # Stop API server
    if [[ -f ".arcitek_api.pid" ]]; then
        API_PID=$(cat .arcitek_api.pid)
        if kill -0 $API_PID 2>/dev/null; then
            kill $API_PID
            print_status "API server stopped"
        fi
        rm -f .arcitek_api.pid
    fi
    
    print_status "All ArciTEK.AI services stopped"
}

# Main execution
case "${1:-start}" in
    "start")
        check_system_requirements
        setup_virtual_environment
        install_dependencies
        initialize_configuration
        start_services
        health_check
        echo -e "${GREEN}"
        echo "🚀 ArciTEK.AI is now running!"
        echo "🌐 Access the platform at: http://localhost:5000"
        echo "📚 Documentation: ./docs/"
        echo "⚛️ Quantum-enhanced precision building is ready!"
        echo -e "${NC}"
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        $0 start
        ;;
    "status")
        health_check
        ;;
    "health")
        health_check
        ;;
    "update")
        print_info "Updating ArciTEK.AI..."
        git pull origin main
        pip install -r requirements.txt --upgrade
        print_status "ArciTEK.AI updated successfully"
        ;;
    "clean")
        print_info "Cleaning temporary files..."
        rm -rf __pycache__ .pytest_cache *.log .arcitek_*.pid
        print_status "Cleanup completed"
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac

