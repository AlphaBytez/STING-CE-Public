# STING CE (Community Edition)

> **Secure Trusted Intelligence and Networking Guardian**
>
> Developed by [AlphaBytez](https://github.com/alphabytez)
>
> *Bee Smart. Bee Secure.*

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![AlphaBytez](https://img.shields.io/badge/by-AlphaBytez-blue.svg)](https://github.com/alphabytez)

Self-hosted platform for secure, private LLM deployment with complete data sovereignty. Features innovative "Honey Jar" knowledge management, enterprise-grade authentication, and the Bee AI assistant. Built for organizations that value privacy and control over their AI infrastructure.

<p align="center">
  <img src="assets/screenshots/dashboard-v1.png" alt="STING-CE Dashboard" width="750"/>
</p>

## ✨ Features

### 🔐 Modern Authentication
- **Passwordless Authentication** - Magic links and WebAuthn/Passkeys
- **Multi-Factor Authentication** - TOTP, SMS, and biometric options
- **Email Verification** - Built-in with automatic validation
- **Session Management** - AAL2 (Two-factor) session controls
- **OAuth2/OIDC** - Standard protocol support via Ory Kratos

### 🍯 Honey Jar Knowledge Management
- **Semantic Search** - Vector-based knowledge retrieval with ChromaDB
- **Multi-Format Support** - PDF, DOCX, HTML, JSON, Markdown, TXT
- **Private & Secure** - Your data stays on your infrastructure
- **Bee Integration** - AI assistant queries your knowledge bases for context
- **Background Processing** - Automatic document chunking and embedding

<p align="center">
  <img src="assets/screenshots/honey-jar-creation.gif" alt="Honey Jar Knowledge Management" width="750"/>
</p>

### 🤖 AI-Powered Assistant (Bee)
- **Intelligent Chat Interface** - Natural language queries with Bee (B. Sting)
- **Knowledge Base Integration** - ChromaDB-powered context retrieval from Honey Jars
- **Multi-LLM Support** - Works with Ollama, OpenAI, LM Studio, vLLM
- **Contextual Responses** - Bee leverages your knowledge bases for accurate answers

<p align="center">
  <img src="assets/screenshots/bee-chat-interface.gif" alt="Bee AI Assistant Chat Interface" width="750"/>
</p>

### 🔒 Security & Privacy
- **Vault Integration** - HashiCorp Vault for secrets management
- **PII Protection** - Automatic serialization for sensitive data
- **Audit Logging** - Comprehensive security event tracking
- **Zero-Trust Architecture** - All services isolated and authenticated

### 🐳 Easy Deployment
- **Docker-Based** - One-command deployment
- **Web Setup Wizard** - Interactive first-run configuration
- **Automatic Validation** - Built-in health checks for all services
- **Hot Reload** - Development mode with live updates

### 🎨 Modern UI & Theming
- **Glass Morphism Design** - Modern STING theme with floating elements
- **Responsive Interface** - Optimized for desktop, tablet, and mobile
- **Multiple Themes** - Customizable themes including modern glass, retro terminal, and more
- **Accessibility** - WCAG-compliant design with keyboard navigation
- **Dark Mode Support** - Built-in support for light and dark themes

## 🚧 Development Status

**STING-CE is under active development!** While the core platform is functional and deployable, not all features listed above are fully enabled or production-ready. Some features may require additional configuration, bug fixes, or implementation work.

**We need your help!** 🤝

- 🐛 **Found a bug?** Please [open an issue](https://github.com/AlphaBytez/STING-CE-Public/issues)
- 💡 **Have an idea?** We'd love to hear it - [create a feature request](https://github.com/AlphaBytez/STING-CE-Public/issues/new)
- 🔧 **Want to contribute?** Pull requests are always welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)
- 📖 **Improving docs?** Documentation PRs are especially appreciated

Every contribution matters - from reporting issues to improving documentation to submitting code. This is a community project, and we welcome developers of all skill levels!

## 🚀 Quick Start

### Prerequisites

- **OS**: Ubuntu 20.04+, Debian 11+, macOS, or WSL2
- **RAM**: 8GB minimum (16GB recommended)
- **CPU**: 4 cores minimum
- **Disk**: 50GB free space
- **Docker**: Installed automatically if not present

### Installation (One-Line Install)

The fastest way to get started is with our bootstrap installer:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/AlphaBytez/STING-CE-Public/main/bootstrap.sh)"
```

This single command will:
- Detect your platform (macOS, WSL, Debian/Ubuntu)
- Clone the repository
- Launch the web-based setup wizard

### Installation (Manual)

Prefer to clone manually? No problem:

```bash
# Clone the repository
git clone https://github.com/AlphaBytez/STING-CE-Public.git
cd STING-CE-Public

# Run the installer (includes web wizard)
./install_sting.sh
```

**The installer will:**
1. ✅ Check system requirements
2. ✅ Install Docker (if needed)
3. ✅ Launch the web setup wizard at `http://localhost:8335`
4. ✅ Guide you through configuration (domain, email, LLM settings)
5. ✅ Install and start all services
6. ✅ Validate email delivery
7. ✅ Create your admin account

**After installation:**
- **Frontend**: https://sting.local:8443
- **API**: https://sting.local:5050
- **Mailpit** (dev mode): http://sting.local:8025

### Upgrading/Reinstalling

If you already have STING-CE installed and want to upgrade or reinstall:

```bash
cd STING-CE-Public

# Reinstall (preserves your data and configuration)
./manage_sting.sh reinstall

# Fresh install (removes everything - use with caution!)
./manage_sting.sh reinstall --fresh
```

**Note:** Running `./install_sting.sh` on an existing installation will detect this and direct you to use the reinstall command instead.

### Installation (Command Line)

For headless servers or automated deployments:

```bash
# Clone the repository
git clone https://github.com/AlphaBytez/STING-CE-Public.git
cd STING-CE-Public

# Create configuration from template
cp STING/conf/config.yml.default STING/conf/config.yml

# Edit configuration (set domain, email settings, etc.)
nano STING/conf/config.yml

# Run installer in non-interactive mode
./install_sting.sh --non-interactive

# Start services
./manage_sting.sh start
```

## 📖 Documentation

### 🌐 Documentation Website

Visit our comprehensive documentation site for a better reading experience:

**[docs.sting.alphabytez.dev](https://alphabytez.github.io/sting-docs/)** (Coming Soon)

Features:
- 🔍 Full-text search across all documentation
- 📱 Mobile-friendly responsive design
- 🌓 Dark/light mode support
- 📚 Version-specific documentation
- 💻 Code examples and API reference

### 📂 Documentation in Repository

Documentation is also available in the `STING/docs/` directory:

- **Installation**: [STING/docs/README.md](STING/docs/README.md) or [Fresh Install Guide](STING/docs/platform/guides/fresh-install-guide.md)
- **Configuration**: [STING/docs/operations/](STING/docs/operations/)
- **API Reference**: [STING/docs/api/](STING/docs/api/)
- **Architecture**: [STING/docs/architecture/](STING/docs/architecture/)
- **Security**: [SECURITY.md](SECURITY.md)

## 🛠️ Management

### Service Management

```bash
# Start all services
./manage_sting.sh start

# Stop all services
./manage_sting.sh stop

# Restart a specific service
./manage_sting.sh restart [service]

# View logs
./manage_sting.sh logs [service]

# Check service status
./manage_sting.sh status
```

## 🏗️ Architecture

STING-CE uses a microservices architecture:

- **Frontend**: React-based UI with Vite
- **API**: Flask REST API with PII protection
- **Kratos**: Ory Kratos for authentication flows
- **Vault**: HashiCorp Vault for secrets
- **Bee**: AI assistant chatbot (B. Sting)
- **Knowledge**: ChromaDB vector database for Honey Jars
- **Database**: PostgreSQL for application data
- **Redis**: Caching and session storage
- **Mailpit**: Development email catcher

## 🐛 Troubleshooting

### Common Issues

**Email Delivery Not Working**
```bash
python3 STING/scripts/health/validate_mailpit.py
```

**Docker Permission Denied**
```bash
sudo usermod -aG docker $USER
# Logout and login again
```

**Port Already in Use**
```bash
# Find what's using the port
sudo lsof -i :8443

# Change port in config.yml or kill the process
```

**Services Not Starting**
```bash
# Check logs
./manage_sting.sh logs

# Check system resources
free -h
df -h

# Restart with cleanup
./manage_sting.sh restart
```

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🔒 Security

Security is our top priority. Please see [SECURITY.md](SECURITY.md) for:
- Reporting vulnerabilities
- Security best practices
- Supported versions
- Disclosure policy

**DO NOT** create public issues for security vulnerabilities.

## 📜 License

STING-CE is released under the [Apache License 2.0](LICENSE).

```
Copyright 2024 AlphaBytez and the STING-CE Community

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## 🏢 About AlphaBytez

STING-CE is developed and maintained by **AlphaBytez**, a software development company focused on security, authentication, and AI-powered solutions.

> *Bee Smart. Bee Secure.*

- **Contact**: [olliec@alphabytez.dev](mailto:olliec@alphabytez.dev)
- **Security**: [security@alphabytez.dev](mailto:security@alphabytez.dev)
- **GitHub**: [@AlphaBytez](https://github.com/AlphaBytez)

## 🙏 Acknowledgments

STING-CE is built on the shoulders of giants. We're grateful to the open-source community and these outstanding projects:

### Core Infrastructure
- **[Ory Kratos](https://www.ory.sh/kratos/)** - Identity and authentication management with WebAuthn support
- **[HashiCorp Vault](https://www.vaultproject.io/)** - Enterprise-grade secrets management
- **[Docker](https://www.docker.com/)** - Containerization platform for simplified deployment
- **[PostgreSQL](https://www.postgresql.org/)** - Reliable, powerful relational database
- **[Redis](https://redis.io/)** - In-memory data structure store for caching and sessions

### AI & Knowledge Management
- **[Ollama](https://ollama.ai/)** - Simplified local LLM deployment and management
- **[ChromaDB](https://www.trychroma.com/)** - Open-source vector database for embeddings
- **[Sentence Transformers](https://www.sbert.net/)** - State-of-the-art sentence embeddings

### Application Framework
- **[Flask](https://flask.palletsprojects.com/)** - Lightweight Python web framework for our API
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python framework for knowledge services
- **[React](https://react.dev/)** - Component-based UI library
- **[Vite](https://vitejs.dev/)** - Fast frontend build tool
- **[Material-UI](https://mui.com/)** - React component library

### Development Tools
- **[Mailpit](https://github.com/axllent/mailpit)** - Email testing tool for development
- **[Grafana](https://grafana.com/)** - Observability and monitoring dashboards
- **[Loki](https://grafana.com/oss/loki/)** - Log aggregation system

### Documentation
- **[Hugo](https://gohugo.io/)** - Fast and flexible static site generator for building our documentation site
- **[Docsy](https://www.docsy.dev/)** - Google's beautiful documentation theme for Hugo with search and versioning

### Community
Special thanks to:
- The Ory community for excellent authentication patterns
- The ChromaDB team for vector database innovation
- The Ollama project for making LLMs accessible
- All open-source contributors who make projects like STING possible

See [CREDITS.md](CREDITS.md) for the complete list of third-party libraries and licenses.

## 📊 Project Status

- **Version**: 1.0.0-ce ([Changelog](CHANGELOG.md))
- **Status**: Active Development
- **Platforms**: Linux (Ubuntu/Debian), macOS, WSL2
- **License**: Apache 2.0 ([View License](LICENSE))
- **Languages**: Python 3.11+, JavaScript (React)
- **Release Date**: October 2025

---

<div align="center">

<a href="https://github.com/alphabytez">
  <img src="docs/assets/alphabytez-logo.svg" alt="AlphaBytez" width="300">
</a>

Made with ❤️ by **[AlphaBytez](https://github.com/alphabytez)** and the STING-CE Community

*Bee Smart. Bee Secure.*

**Quick Install**:
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/AlphaBytez/STING-CE-Public/main/bootstrap.sh)"
```

<br/>
<br/>

</div>
