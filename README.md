# 🐙 GitHub Issue Analyzer with Streamlit Interface

A powerful tool that analyzes GitHub issues using AI and provides automated fixes with a beautiful Streamlit web interface.

## Features

- 🔍 **AI-Powered Issue Analysis**: Analyze GitHub issues with detailed technical analysis
- 📊 **Interactive Dashboards**: Visualize issue statistics and trends
- 🚀 **Auto-Fix Capability**: Automatically generate fixes and create pull requests
- 📈 **Real-time Monitoring**: Track auto-fix task progress
- 🎯 **Individual Issue Analysis**: Deep dive into specific issues
- 📋 **Repository Statistics**: Comprehensive repository insights

## Prerequisites

- Python 3.8+
- GitHub account with repository access
- OpenAI API key
- Composio API key

## Installation

### Option 1: Automated Installation (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd GDev-main
   ```

2. **Run the installation script**:
   ```bash
   python install.py
   ```

3. **Edit the .env file**:
   Add your API keys to the `.env` file:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   COMPOSIO_API_KEY=your_composio_api_key_here
   ```

### Option 2: Manual Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd GDev-main
   ```

2. **Install core dependencies**:
   ```bash
   pip install fastapi uvicorn openai python-dotenv pydantic streamlit requests pandas plotly python-multipart
   ```

3. **Install optional dependencies** (if needed):
   ```bash
   pip install composio composio-openai langchain langchain-openai
   ```

4. **Create .env file**:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   COMPOSIO_API_KEY=your_composio_api_key_here
   ```

## Usage

### 1. Start the API Server

First, start the FastAPI server that provides the backend functionality:

```bash
python src/main.py
```

The API will be available at `http://localhost:8000`

**Note**: On first run, you'll need to authorize GitHub access. Follow the URL provided in the console output.

### 2. Start the Streamlit App

In a new terminal window, start the Streamlit interface:

```bash
streamlit run streamlit_app.py
```

The Streamlit app will be available at `http://localhost:8501`

## Streamlit App Features

### 📊 Repository Analysis
- Enter repository owner and name
- View comprehensive issue statistics
- Analyze issues with AI-powered insights
- Visualize priority and complexity distributions
- Search and filter issues

### 🔍 Individual Issue Analysis
- Analyze specific issues by number
- Get detailed technical analysis
- View suggested solutions
- Start auto-fix processes

### 🚀 Auto-fix Issues
- Start automated fix processes
- Monitor task progress in real-time
- View generated pull request URLs
- Track multiple auto-fix tasks

### 🏥 API Health
- Monitor API connection status
- View GitHub integration status
- Check available tools
- Monitor active auto-fix tasks

## API Endpoints

The backend provides the following endpoints:

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /repository/{owner}/{repo}/issues` - Get analyzed issues
- `GET /repository/{owner}/{repo}/issues/raw` - Get raw issues
- `GET /repository/{owner}/{repo}/issues/{issue_number}` - Analyze specific issue
- `GET /repository/{owner}/{repo}/issues/stats` - Get issue statistics
- `POST /repository/{owner}/{repo}/issues/{issue_number}/auto-fix` - Start auto-fix
- `GET /auto-fix/{task_id}` - Get auto-fix status

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key for AI analysis
- `COMPOSIO_API_KEY`: Your Composio API key for GitHub integration

### API Configuration

The API runs on `http://localhost:8000` by default. You can modify the base URL in `streamlit_app.py` if needed:

```python
API_BASE_URL = "http://localhost:8000"
```

## Troubleshooting

### Common Issues

1. **API Connection Error**:
   - Ensure the API server is running (`python src/main.py`)
   - Check if port 8000 is available
   - Verify the API_BASE_URL in streamlit_app.py

2. **GitHub Authorization**:
   - Follow the authorization URL provided in the console
   - Ensure your GitHub account has access to the repositories

3. **Missing Dependencies**:
   - Run `pip install -r requirements.txt`
   - Ensure Python 3.8+ is installed

4. **Auto-fix Failures**:
   - Check repository permissions
   - Ensure the repository is accessible
   - Verify branch naming conventions

### Debug Mode

To run the API with debug information:

```bash
python src/main.py --debug
```

## Development

### Project Structure

```
GDev-main/
├── src/
│   ├── main.py              # FastAPI server
│   ├── pr_list.py           # PR management
│   └── slack_notification.py # Notifications
├── streamlit_app.py         # Streamlit interface
├── requirements.txt         # Dependencies
└── README.md              # This file
```

### Adding New Features

1. **API Endpoints**: Add new endpoints in `src/main.py`
2. **Streamlit Pages**: Add new pages in `streamlit_app.py`
3. **Dependencies**: Update `requirements.txt`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Check the troubleshooting section
- Review the API documentation at `http://localhost:8000/docs`
- Open an issue on GitHub

---

**Happy Issue Analyzing! 🐙✨** 