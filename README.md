# Smart ROM Cache Manager

A cross-platform, intelligent caching system for retro gaming ROM collections. Seamlessly integrates with EmulationStation to provide on-demand ROM downloading with smart cleanup and prioritization.

## Features

- 🚀 **On-demand ROM caching** - Download only what you play
- 🧠 **Smart cleanup** - LRU eviction with platform/favorite prioritization  
- 🖥️ **Cross-platform** - Linux, macOS, Windows support
- 🔗 **EmulationStation integration** - Transparent ROM access
- 📊 **Web dashboard** - Monitor and manage your cache
- 🐳 **Docker ready** - Easy deployment and configuration
- 🌐 **Multiple backends** - HTTP, SMB, Jellyfin, S3 support

## Quick Start
```bash
# Clone the repository
git clone https://github.com/yourusername/smart-rom-cache.git
cd smart-rom-cache

# Install dependencies
pip install -r requirements.txt

# Run tests
python tests/integration_test_suite.py

# Basic usage
python src/main.py --config config/config.yaml