# Contributing to ArciTEK.AI

Welcome to ArciTEK.AI! We're excited that you're interested in contributing to our quantum-enhanced AI development platform. This guide will help you get started.

> **"Every build is a work of art"** - infinite♾2025

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

ArciTEK.AI is committed to providing a welcoming and inclusive environment for all contributors. We expect all participants to:

- **Be respectful** and considerate in all interactions
- **Be collaborative** and help others learn and grow
- **Be professional** in communication and code reviews
- **Focus on what is best** for the community and the project

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.11+** - Core backend language
- **Node.js 22+** - Frontend and tooling
- **Git** - Version control
- **Docker** (optional) - For containerized development

### Fork and Clone

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/ArciTEK.AI.git
cd ArciTEK.AI
```

3. **Add upstream** remote:

```bash
git remote add upstream https://github.com/NaTo1000/ArciTEK.AI.git
```

## Development Setup

### Quick Start

Run the automated setup script:

```bash
./startup.sh
```

This will:
- Check system requirements
- Install dependencies
- Run the configuration wizard
- Initialize quantum platforms and AI models
- Start the development server

### Manual Setup

If you prefer manual setup:

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install Node.js dependencies
npm install

# Configure the platform
./startup.sh config

# Start development server
./startup.sh start
```

### Configuration

ArciTEK.AI requires API keys for quantum computing platforms and AI models. The configuration wizard will guide you through setup, or you can manually edit `config/.env`:

```bash
# Quantum Computing Platforms
IBM_QUANTUM_TOKEN=your_token_here
IONQ_API_KEY=your_key_here

# AI Model Integrations
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

**Note:** Never commit API keys to the repository. They are automatically excluded via `.gitignore`.

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

#### 🐛 Bug Reports

Found a bug? Please create an issue with:
- Clear, descriptive title
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (OS, Python version, etc.)
- Screenshots or logs if applicable

#### ✨ Feature Requests

Have an idea? Create an issue with:
- Clear description of the feature
- Use cases and benefits
- Proposed implementation (if you have ideas)
- Any relevant examples or mockups

#### 📝 Documentation

Documentation improvements are always welcome:
- Fix typos or clarify existing docs
- Add examples and tutorials
- Improve API documentation
- Translate documentation

#### 💻 Code Contributions

Ready to code? Great! See the [Pull Request Process](#pull-request-process) below.

### Finding Issues to Work On

Look for issues labeled:
- `good first issue` - Great for newcomers
- `help wanted` - We need community help
- `bug` - Bug fixes needed
- `enhancement` - New features to implement

## Coding Standards

### Python Code Style

We follow **PEP 8** with some modifications:

```python
# Good: Clear, descriptive names
def calculate_quantum_boost_percentage(circuit_depth: int, qubit_count: int) -> float:
    """
    Calculate quantum performance boost percentage.
    
    Args:
        circuit_depth: Depth of the quantum circuit
        qubit_count: Number of qubits in the system
        
    Returns:
        Boost percentage as a float
    """
    base_boost = 1.267  # 26.7% base boost
    return base_boost * (circuit_depth / 100) * (qubit_count / 10)

# Bad: Unclear, abbreviated names
def calc_qb(cd, qc):
    return 1.267 * (cd/100) * (qc/10)
```

**Key principles:**
- Use type hints for all function parameters and returns
- Write comprehensive docstrings (Google style)
- Maximum line length: 100 characters
- Use meaningful variable names
- Keep functions focused and single-purpose

### JavaScript/TypeScript Code Style

We follow **Airbnb JavaScript Style Guide**:

```typescript
// Good: Clear, typed, documented
interface QuantumCircuit {
  depth: number;
  qubitCount: number;
  gates: QuantumGate[];
}

/**
 * Optimize quantum circuit for execution
 * @param circuit - The quantum circuit to optimize
 * @returns Optimized circuit
 */
function optimizeCircuit(circuit: QuantumCircuit): QuantumCircuit {
  // Implementation
  return optimizedCircuit;
}

// Bad: Unclear, untyped
function opt(c) {
  return c;
}
```

### Commit Messages

Write clear, descriptive commit messages:

```bash
# Good
feat: Add IBM Quantum integration with Qiskit
fix: Resolve precision calculation in build system
docs: Update API documentation for SupersynapAI
test: Add unit tests for quantum orchestration layer

# Bad
update stuff
fix bug
changes
```

**Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting, etc.)
- `refactor` - Code refactoring
- `test` - Adding or updating tests
- `chore` - Maintenance tasks

## Testing Guidelines

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/

# Run specific test file
python3 -m pytest tests/test_quantum_orchestration.py

# Run with coverage
python3 -m pytest --cov=arcitek_core tests/
```

### Writing Tests

Every new feature or bug fix should include tests:

```python
import pytest
from arcitek_core.quantum import QuantumOrchestrator

def test_quantum_orchestrator_initialization():
    """Test quantum orchestrator initializes correctly"""
    orchestrator = QuantumOrchestrator()
    assert orchestrator is not None
    assert orchestrator.platforms == 5

def test_quantum_boost_calculation():
    """Test quantum boost percentage calculation"""
    orchestrator = QuantumOrchestrator()
    boost = orchestrator.calculate_boost(circuit_depth=100, qubits=10)
    assert boost == pytest.approx(26.7, rel=0.1)
```

**Testing principles:**
- Write tests before fixing bugs (TDD)
- Aim for >80% code coverage
- Test edge cases and error conditions
- Use descriptive test names
- Keep tests isolated and independent

## Pull Request Process

### 1. Create a Branch

Create a feature branch from `main`:

```bash
git checkout -b feature/quantum-error-correction
```

**Branch naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/updates

### 2. Make Your Changes

- Write clean, well-documented code
- Follow coding standards
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run tests
python3 -m pytest tests/

# Check code style
flake8 arcitek_core/
black --check arcitek_core/

# Type checking
mypy arcitek_core/
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: Add quantum error correction module"
```

### 5. Push to Your Fork

```bash
git push origin feature/quantum-error-correction
```

### 6. Create Pull Request

1. Go to your fork on GitHub
2. Click "New Pull Request"
3. Select your feature branch
4. Fill out the PR template with:
   - Clear description of changes
   - Related issue numbers
   - Testing performed
   - Screenshots (if UI changes)

### 7. Code Review

- Respond to review comments promptly
- Make requested changes
- Push updates to your branch
- Request re-review when ready

### 8. Merge

Once approved, a maintainer will merge your PR. Congratulations! 🎉

## Project Structure

```
ArciTEK.AI/
├── arcitek_core/          # Core platform code
│   ├── __init__.py
│   ├── main.py            # Main application entry
│   ├── api/               # API endpoints
│   ├── models/            # Data models
│   └── utils/             # Utility functions
├── quantum/               # Quantum computing integration
│   ├── orchestration_layer.py
│   ├── ibm_quantum.py
│   ├── ionq.py
│   └── ...
├── ai_models/             # AI model factory
│   ├── model_factory.py
│   ├── supersynap_ai.py
│   ├── argo_bots.py
│   └── chimera.py
├── tools/                 # Development tools
├── scripts/               # Utility scripts
│   ├── config_wizard.py
│   ├── upgrade.py
│   └── migrate.py
├── tests/                 # Test suite
├── docs/                  # Documentation
├── .github/               # GitHub workflows
│   └── workflows/
│       └── ci.yml
├── config/                # Configuration files
├── requirements.txt       # Python dependencies
├── package.json           # Node.js dependencies
├── startup.sh             # Startup script
└── README.md
```

## Community

### Communication Channels

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - General questions and ideas
- **Pull Requests** - Code contributions and reviews

### Getting Help

If you need help:

1. Check the [documentation](docs/)
2. Search existing [issues](https://github.com/NaTo1000/ArciTEK.AI/issues)
3. Ask in [GitHub Discussions](https://github.com/NaTo1000/ArciTEK.AI/discussions)
4. Create a new issue with the `question` label

### Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- Release notes
- Project documentation

## License

By contributing to ArciTEK.AI, you agree that your contributions will be licensed under the same license as the project.

---

## Quick Reference

### Common Commands

```bash
# Start development server
./startup.sh start

# Run tests
python3 -m pytest tests/

# Check code style
flake8 arcitek_core/

# Format code
black arcitek_core/

# Update dependencies
pip3 install -r requirements.txt

# Check for updates
./startup.sh update
```

### Useful Resources

- [ArciTEK.AI Documentation](docs/)
- [API Reference](docs/API.md)
- [Architecture Guide](docs/ARCHITECTURE.md)
- [Quantum Integration Guide](docs/QUANTUM.md)
- [AI Models Guide](docs/AI_MODELS.md)

---

**Thank you for contributing to ArciTEK.AI!** 🚀

*"Every build is a work of art"* - infinite♾2025
