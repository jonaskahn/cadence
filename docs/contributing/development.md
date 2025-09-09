# Development Setup

## Prerequisites

- Python 3.13+ (required)
- Poetry for dependency management
- Git for version control

## Setup Instructions

1. **Clone the repository**

   ```bash
   git clone https://github.com/jonaskahn/cadence.git
   cd cadence
   ```

2. **Install dependencies**

   ```bash
   poetry install
   poetry install --with docs  # For documentation development
   ```

3. **Set up environment**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the application**

   ```bash
   poetry run python -m cadence start all
   ```

5. **Run tests**

   ```bash
   poetry run pytest
   ```

6. **Build documentation**
   ```bash
   poetry run mkdocs serve  # Live reload at http://localhost:8000
   poetry run mkdocs build  # Build static site
   ```

## Development Workflow

1. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

    - Follow the code style guidelines
    - Add tests for new functionality
    - Update documentation as needed

3. **Run quality checks**

   ```bash
   poetry run black .
   poetry run isort .
   poetry run mypy .
   poetry run pytest
   ```

4. **Commit and push**

   ```bash
   git add .
   git commit -m "feat: add your feature"
   git push origin feature/your-feature-name
   ```

5. **Create a pull request**
    - Use the GitHub web interface
    - Provide a clear description of changes
    - Reference any related issues
