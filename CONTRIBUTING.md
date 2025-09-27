# Contribution Guidelines 🤝

Hello, and thank you for your interest in contributing to **archpkg-helper**! 🎉  
We are excited to have you here and welcome all contributions — big or small.  

This document will help you get started by explaining how to set up the project locally, the process of making contributions, and the best practices we follow. By contributing, you are helping us improve this CLI tool and make package searching and installation smoother for the community. 💡  

---

## ✨ About archpkg-helper  

archpkg-helper is a **command-line interface (CLI) tool** designed to search and generate install commands for Linux packages from multiple sources:  

- Arch Linux official repositories (**pacman**)  
- Arch User Repository (**AUR**)  
- Flatpak (**flathub**)  

It supports **fuzzy matching, filtering, and interactive prompts**, helping users quickly find and install packages with the correct commands.  

---

## 🛠️ Setting Up the Project Locally  

Before contributing, please make sure you can run the project locally.  

### 1. Fork the Repository  
- Visit the [archpkg-helper repository](https://github.com/AdmGenSameer/archpkg-helper).  
- Click the **Fork** button in the top-right corner to create your own copy.  

### 2. Clone Your Fork  
```bash
git clone https://github.com/<your-username>/archpkg-helper.git
cd archpkg-helper 
```
### 3. Add the Upstream Remote

This ensures you can keep your fork in sync with the original repository.
```bash
git remote add upstream https://github.com/AdmGenSameer/archpkg-helper.git
git remote -v
```
### 4. Install Python & pip
Ensure you have Python 3.6+ and pip installed :
```bash
python3 --version
pip3 --version
```
### 5. Install the Package

For normal installation:
```bash
pip install .
```

For development mode:
```bash
pip install -e .
```
### 6. Install System Dependencies

Depending on your Linux distribution:

- Arch Linux / Manjaro
   - pacman is pre-installed.
   - Install yay for AUR support:
       ```bash
       sudo pacman -S yay
       ```
   - Install flatpak if needed:
      ```bash
      sudo pacman -S flatpak
      ```

- Ubuntu / Linux Mint / Debian
```bash
sudo apt update
sudo apt install flatpak
```

- Fedora
``` bash
sudo dnf install flatpak
```
- openSUSE
```bash
sudo zypper install flatpak
```
Now you are ready to start contributing! 🚀

---
## 🌿 Branching Strategy

We recommend creating a new branch for each contribution. This keeps your work organized and easier to review.
``` bash
git checkout -b <branch-name>
```
Examples:

- docs/add-contribution-guide
- feat/improve-fuzzy-search
- fix/flatpak-command-error

## ✍️ Commit Message Guidelines

We follow Conventional Commits to maintain clarity:

- feat : → Adding a new feature
- fix : → Fixing a bug
- docs : → Documentation only changes
- chore : → Maintenance tasks or config updates

Examples:
- docs: add detailed contribution guidelines
- feat: implement interactive multi-package selection
- fix: resolve flatpak dependency issue on Fedora
  
Polite request: Please keep your commits descriptive and meaningful, so everyone can easily understand your changes. 

## Final Note

We truly appreciate your willingness to contribute to **archpkg-helper**.
Your contributions, no matter how small, make this project more useful for the Linux community worldwide.

If you ever feel unsure about something, don’t hesitate to ask questions by opening an issue or discussion. Collaboration and learning go      hand in hand, and we are here to support you. ❤️

Thank you again for being here and helping us grow this project.
Happy contributing! ✨