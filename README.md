# 🚀 archpkg-helper

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/AdmGenSameer/archpkg-helper/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue)](https://www.python.org/)
[![Issues](https://img.shields.io/github/issues/AdmGenSameer/archpkg-helper)](https://github.com/AdmGenSameer/archpkg-helper/issues)
[![Forks](https://img.shields.io/github/forks/AdmGenSameer/archpkg-helper?style=social)](https://github.com/AdmGenSameer/archpkg-helper/network/members)
[![Stars](https://img.shields.io/github/stars/AdmGenSameer/archpkg-helper?style=social)](https://github.com/AdmGenSameer/archpkg-helper/stargazers)

A **command-line utility** for simplifying package management on Linux distributions.  
This project aims to make installing, removing, and searching for packages easier,  
and welcomes contributions from the open source community. ✨

---

## 📖 Table of Contents

- [ℹ️ About](#ℹ️-about)
- [✨ Features](#-features)
- [⚙️ Installation](#️-installation)
- [💻 Usage](#-usage)
- [📂 File Structure](#-file-structure)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)

---

## ℹ️ About

**archpkg-helper** is designed for users who want an easier way to manage packages on Linux systems.  
While originally inspired by Arch Linux, this tool aims to work on **any Linux distribution** that supports Python and common package managers.  

👉 Whether you’re **new to Linux** or a **seasoned user**, this tool offers simple commands for common package operations.

---

## ✨ Features

✅ Install, remove, and search for packages with simple commands  
✅ Support for dependencies and AUR packages *(coming soon)*  
✅ Easy-to-read output and error messages  
✅ Cross-distro support – **not bound to Arch Linux**  

---

## ⚙️ Installation

You can install **archpkg-helper** on any Linux distro.

### 📋 Prerequisites
- Python **3.6+**
- `git` installed

### 🛠 Steps

```sh
git clone https://github.com/AdmGenSameer/archpkg-helper.git
cd archpkg-helper
pip install .
For development mode:

sh
Copy code
pip install -e .
💻 Usage
After installation, use the following commands:

sh
Copy code
archpkg-helper install <package-name>
archpkg-helper remove <package-name>
archpkg-helper search <package-name>
🔹 Replace <package-name> with the package you want to manage.

📂 File Structure
bash
Copy code
archpkg-helper/
│
├── archpkg_helper/        # Main Python package
│   ├── __init__.py
│   ├── cli.py             # Command-line interface implementation
│   ├── core.py            # Core logic for package management
│   └── utils.py           # Utility functions
│
├── tests/                 # Unit tests
│   ├── test_cli.py
│   └── test_core.py
│
├── setup.py               # Python packaging configuration
├── LICENSE                # Project license (Apache 2.0)
├── README.md              # This file
└── CONTRIBUTING.md        # Contribution guidelines
🤝 Contributing
We welcome contributions! 🙌
Please read our CONTRIBUTING.md for guidelines.

📝 How to Contribute
Fork the repository

Create a branch: git checkout -b feature-branch

Make your changes and commit: git commit -m "Describe your changes"

Push to your fork: git push origin feature-branch

Open a Pull Request

🐞 Report bugs or request features here.

📜 License
This project is licensed under the Apache License 2.0.

⭐️ If you like this project, consider giving it a star on GitHub!
Happy hacking! 🐧💻