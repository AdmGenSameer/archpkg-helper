# Contributing to archpkg-helper

Thank you for your interest in contributing to **archpkg-helper**! 🎉 

We welcome contributions of all kinds - whether you're fixing bugs, adding features, improving documentation, or helping with testing. This guide will help you get started and ensure your contributions can be reviewed and merged efficiently.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Contributions](#making-contributions)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Getting Help](#getting-help)

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful, inclusive, and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.6 or higher
- Git
- A GitHub account

### First-Time Setup

1. **Fork the repository**
   - Visit the [archpkg-helper repository](https://github.com/AdmGenSameer/archpkg-helper)
   - Click the "Fork" button to create your own copy

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/archpkg-helper.git
   cd archpkg-helper
   ```

3. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/AdmGenSameer/archpkg-helper.git
   ```

4. **Verify your setup**
   ```bash
   git remote -v
   # Should show both origin (your fork) and upstream (original repo)
   ```

## Development Setup

### Environment Setup

We recommend using `pipx` for development to avoid conflicts with system packages:

1. **Install pipx** (if not already installed)
   ```bash
   # Arch Linux
   sudo pacman -S pipx
   pipx ensurepath

   # Ubuntu/Debian
   sudo apt install pipx
   pipx ensurepath

   # Fedora
   sudo dnf install pipx
   pipx ensurepath
   ```

2. **Install in development mode**
   ```bash
   # For development with editable installation
   pipx install -e .
   
   # Or using pip in user mode
   python3 -m pip install --user -e .
   ```

3. **Install system dependencies**
   
   Depending on your distribution:
   
   **Arch Linux/Manjaro:**
   ```bash
   # pacman is pre-installed
   # Install AUR helper (optional but recommended for testing)
   sudo pacman -S yay
   # Install flatpak if needed
   sudo pacman -S flatpak
   ```
   
   **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install flatpak
   ```
   
   **Fedora:**
   ```bash
   sudo dnf install flatpak
   ```

4. **Verify installation**
   ```bash
   archpkg --version
   archpkg --help
   ```

### Keeping Your Fork Updated

Regularly sync your fork with the upstream repository:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

## Making Contributions

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes** - Fix issues or unexpected behavior
- **Feature additions** - Add new functionality
- **Documentation** - Improve README, add examples, or API docs
- **Testing** - Add or improve test coverage
- **Performance** - Optimize existing functionality
- **Refactoring** - Improve code structure without changing functionality

### Before You Start

1. **Check existing issues** - Look for related issues or feature requests
2. **Create an issue** - For significant changes, create an issue first to discuss your approach
3. **Start small** - Consider starting with small contributions to get familiar with the codebase

### Branching Strategy

Create a new branch for each contribution:

```bash
git checkout main
git pull upstream main
git checkout -b your-branch-name
```

**Branch naming conventions:**
- `feat/description` - New features
- `fix/description` - Bug fixes  
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions/improvements
- `chore/description` - Maintenance tasks

## Pull Request Process

### Before Submitting

1. **Test your changes** - Ensure your code works as expected
2. **Update documentation** - Update README.md or relevant docs if needed
3. **Check code style** - Follow the coding standards (see below)
4. **Write meaningful commits** - Use clear, descriptive commit messages

### Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only changes
- `style:` - Code style changes (formatting, semicolons, etc.)
- `refactor:` - Code changes that neither fix bugs nor add features
- `test:` - Adding or modifying tests
- `chore:` - Changes to build process or auxiliary tools

### Submitting Your Pull Request

1. **Push your branch**
   ```bash
   git push origin your-branch-name
   ```

2. **Create Pull Request**
   - Go to your fork on GitHub
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template with:
     - Clear description of changes
     - Link to related issues
     - Testing details
     - Screenshots (if applicable)

3. **Respond to feedback**
   - Address any review comments
   - Make additional commits as needed
   - Keep the conversation constructive

## Coding Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) Python style guide
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small when possible

### Code Organization

- Place new package managers in appropriate modules
- Follow the existing project structure
- Import statements should be organized (standard library, third-party, local)

### Error Handling

- Use appropriate exception handling
- Provide clear error messages to users
- Log errors appropriately for debugging

## Testing

### Running Tests

```bash
# Install test dependencies
pip install -e .[test]

# Run tests
python -m pytest

# Run with coverage
python -m pytest --cov=archpkg
```

### Writing Tests

- Add tests for new features and bug fixes
- Use descriptive test names
- Test edge cases and error conditions
- Place tests in the `tests/` directory

### Manual Testing

Test your changes across different scenarios:
- Different Linux distributions (if possible)
- Various package managers
- Edge cases (empty queries, network issues, etc.)

## Documentation

### Updating Documentation

- Update README.md for user-facing changes
- Add docstrings to new functions and classes
- Update help text for new CLI options
- Consider adding examples for complex features

### Documentation Style

- Use clear, concise language
- Include practical examples
- Keep formatting consistent
- Verify all links work

## Getting Help

### Communication Channels

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - Questions, ideas, general discussion
- **Pull Request Comments** - Code review discussions

### Questions and Support

Don't hesitate to ask questions! We're here to help:

1. Check existing issues and discussions first
2. Create a new issue for bugs or feature requests
3. Start a discussion for questions or ideas
4. Tag maintainers if you need specific guidance

### Maintainer Response

We aim to:
- Acknowledge new issues within 48 hours
- Review pull requests within a week
- Provide constructive feedback
- Help contributors through the process

---

Thank you for contributing to archpkg-helper! Your efforts help make package management easier for Linux users everywhere. 

If you have any questions about this contributing guide or need help with your contribution, please don't hesitate to reach out through GitHub issues or discussions.

Happy contributing! 🚀