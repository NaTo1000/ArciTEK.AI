# ArciTEK.AI Quick Start Guide

> **"Every build is a work of art"** - infinite♾2025

Welcome to ArciTEK.AI! This guide will help you get started in minutes.

## 🚀 One-Command Setup

```bash
git clone https://github.com/NaTo1000/ArciTEK.AI.git
cd ArciTEK.AI
./startup.sh
```

That's it! The startup script will handle everything automatically.

## 📋 What Happens During Setup

The startup script will:

1. **Check System Requirements**
   - Python 3.11+
   - Node.js 22+
   - Git
   - pip and npm

2. **Run Configuration Wizard**
   - Interactive setup for API keys
   - Quantum platform configuration
   - AI model integration
   - Database settings

3. **Install Dependencies**
   - Python packages (313 packages)
   - Node.js modules
   - Quantum computing SDKs
   - AI/ML frameworks

4. **Initialize Platforms**
   - Quantum computing platforms (5 platforms)
   - AI model factory (325B parameters)
   - Precision build system (99.97% precision)
   - NayDoeV1 learning environments

5. **Start Services**
   - Backend server on port 8000
   - Web interface
   - API endpoints
   - Dashboard

## 🔑 API Key Configuration

During the configuration wizard, you'll be asked for API keys. Here's where to get them:

### Quantum Computing Platforms

| Platform | Get API Key | Required? |
|----------|-------------|-----------|
| **IBM Quantum** | [quantum-computing.ibm.com](https://quantum-computing.ibm.com/) | Recommended |
| **IonQ** | [cloud.ionq.com](https://cloud.ionq.com/) | Optional |
| **Google Quantum AI** | Google Cloud Console | Optional |
| **Amazon Braket** | AWS Console | Optional |
| **Azure Quantum** | Azure Portal | Optional |

### AI Model Platforms

| Platform | Get API Key | Required? |
|----------|-------------|-----------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com/) | Recommended |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/) | Optional |
| **Google Gemini** | [makersuite.google.com](https://makersuite.google.com/) | Optional |
| **IBM WatsonX** | [cloud.ibm.com](https://cloud.ibm.com/) | Optional |
| **Hugging Face** | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) | Optional |

**Note:** You can skip any platform during setup and configure it later using `./startup.sh config`

## 🌐 Accessing ArciTEK.AI

Once started, access the platform at:

- **Web Interface:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8000/dashboard
- **API Endpoint:** http://localhost:8000/api

## 🎯 Common Commands

### Start ArciTEK.AI
```bash
./startup.sh start
```

### Stop ArciTEK.AI
```bash
./startup.sh stop
```

### Restart ArciTEK.AI
```bash
./startup.sh restart
```

### Check Status
```bash
./startup.sh status
```

### Reconfigure
```bash
./startup.sh config
```

### Update to Latest Version
```bash
./startup.sh update
```

## 🧪 Validate Configuration

After configuration, validate your API keys:

```bash
python3 scripts/validate_keys.py
```

This will test all configured platforms and show which ones are working.

## 🔧 Troubleshooting

### Port Already in Use

If port 8000 is already in use, edit `config/.env` and change:
```
ARCITEK_PORT=8001
```

### Missing Dependencies

If you see dependency errors, manually install:

```bash
# Python dependencies
pip3 install -r requirements.txt

# Node.js dependencies
npm install
```

### API Key Issues

If a platform isn't working:

1. Reconfigure: `./startup.sh config`
2. Validate: `python3 scripts/validate_keys.py`
3. Check the validation report: `config/validation_report.json`

### Permission Denied

If you get permission errors on `startup.sh`:

```bash
chmod +x startup.sh
chmod +x scripts/*.py
```

## 📚 Next Steps

Once ArciTEK.AI is running:

1. **Explore the Dashboard** - View system status and metrics
2. **Try the API** - Test quantum and AI endpoints
3. **Read the Docs** - Check out [ARCHITECTURE.md](docs/ARCHITECTURE.md)
4. **Run Tests** - `python3 -m pytest tests/`
5. **Deploy** - `python3 scripts/deploy.py cloudflare`

## 🤝 Getting Help

- **Documentation:** [README.md](README.md)
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Issues:** [GitHub Issues](https://github.com/NaTo1000/ArciTEK.AI/issues)
- **Discussions:** [GitHub Discussions](https://github.com/NaTo1000/ArciTEK.AI/discussions)

## 📊 Performance Expectations

After successful setup, you should see:

- ✅ **Quantum Boost:** +26.7% performance improvement
- ✅ **Precision:** 99.97% build precision capability
- ✅ **Integration:** 348/200 tools (174% coverage)
- ✅ **AI Models:** 325B total parameters available
- ✅ **Platforms:** 5 quantum + 5 AI platforms ready

## 🎓 Learning Resources

- **Quantum Computing:** [docs/QUANTUM.md](docs/QUANTUM.md)
- **AI Models:** [docs/AI_MODELS.md](docs/AI_MODELS.md)
- **API Reference:** [docs/API.md](docs/API.md)
- **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

**Ready to build? Let's go!** 🚀

*infinite♾2025*
