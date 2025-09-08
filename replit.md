# Overview

Ultroid is a comprehensive Telegram userbot built on the Telethon framework. It serves as a powerful automation and management tool for Telegram users, offering an extensive plugin system with over 100 different functionalities including media processing, chat management, entertainment features, and administrative tools. The bot operates in both userbot mode (using user account) and assistant bot mode for enhanced capabilities.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Framework
- **Telethon-based**: Built on Telethon library for Telegram Bot API interactions
- **Plugin Architecture**: Modular plugin system with separate directories for core plugins and addons
- **Dual Mode Operation**: Supports both userbot and assistant bot functionality
- **Database Integration**: Uses Redis for data persistence and caching

## Application Structure
- **Main Bot (`ultroid_bot`)**: Primary userbot instance for user commands
- **Assistant Bot (`asst`)**: Secondary bot for inline functionality and advanced features
- **Plugin System**: Organized into official plugins and optional addons
- **Command Handler**: Decorator-based command system with pattern matching

## Key Components

### Database Layer
- **Redis**: Primary database for configuration, user data, and feature settings
- **Database Abstraction**: Custom database wrapper (`udB`) for unified data access
- **Feature-specific DBs**: Specialized database modules for different features (greetings, filters, etc.)

### Media Processing
- **FFmpeg Integration**: Video/audio processing and conversion
- **PIL/OpenCV**: Image manipulation and computer vision features
- **Telegraph**: Image/file hosting for media sharing

### Assistant Features
- **Inline Functionality**: Inline query support for quick actions
- **Callback Handling**: Interactive button-based interfaces
- **Game Integration**: Built-in games and entertainment features
- **Localization**: Multi-language support system

### Security & Administration
- **Permission System**: Role-based access control with sudo and admin levels
- **PM Permit**: Private message filtering and approval system
- **Global Tools**: Cross-chat moderation and management
- **Flood Protection**: Anti-spam and rate limiting

## Configuration Management
- **Environment Variables**: Docker and Heroku deployment support
- **Runtime Configuration**: Dynamic setting changes through commands
- **Feature Toggles**: Granular control over functionality

## Deployment Architecture
- **Containerized**: Docker support for consistent deployment
- **Multi-platform**: Heroku, Okteto, and local deployment options
- **Process Management**: Automatic restart and error recovery

# External Dependencies

## Core Dependencies
- **Telethon**: Telegram MTProto API client library
- **Redis**: In-memory data structure store for caching and persistence
- **aiohttp**: Asynchronous HTTP client/server framework
- **Pillow**: Python Imaging Library for image processing
- **OpenCV**: Computer vision library for advanced image/video processing

## Media Processing
- **FFmpeg**: Command-line multimedia framework
- **youtube-dl/yt-dlp**: Video download and processing
- **Telegraph**: File hosting service for media uploads

## Web Services
- **Google API Client**: Integration with Google services (Drive, Search)
- **BeautifulSoup4**: HTML parsing for web scraping
- **requests**: HTTP library for API interactions

## Utility Libraries
- **python-decouple**: Configuration management
- **GitPython**: Git repository management
- **APScheduler**: Advanced Python Scheduler for background tasks
- **qrcode**: QR code generation and processing

## Optional Services
- **PostgreSQL**: Optional database backend (psycopg2-binary)
- **Google Drive**: Cloud storage integration
- **Various APIs**: Weather, translation, and other third-party services