# 🌱 EcoMind AI

### Intelligent Waste Management System

<p align="center">
  <img src="screenshots/dashboard.png" width="850">
</p>

<p align="center">
  <b>Track waste • Analyze data • Improve sustainability</b>
</p>

---

## 📌 About the Project

**EcoMind AI** is a Python-based desktop application designed to help households and communities record, analyze, and understand their waste.

The system combines **PyQt6, SQLite, data visualization, and AI/ML concepts** in a single interactive application.

Users can record waste, track recycling, view statistics, explore material flow, and receive sustainability recommendations.

---

## 🎯 Problem Statement

Waste is generated every day, but people often have limited visibility into their own waste habits.

Common problems include:

* Difficulty tracking daily waste
* Lack of awareness about high-waste categories
* Poor visibility into recycling activity
* Difficulty understanding waste patterns
* Limited access to simple waste-analysis tools

EcoMind AI provides a centralized platform to make this information easier to record and understand.

---

## 💡 Our Solution

EcoMind AI turns everyday waste records into useful information through a simple desktop interface.

```text
Record Waste
     ↓
Store Data
     ↓
Analyze Data
     ↓
Visualize Results
     ↓
Generate Recommendations
```

---

## ✨ Features

### 🖥️ Interactive Dashboard

The dashboard provides a centralized overview of waste-management activity.

<p align="center">
  <img src="screenshots/dashboard.png" width="850">
</p>

It displays key information such as:

* Total waste
* Recycled waste
* Recycling rate
* Highest waste category
* Waste-reduction information
* Waste statistics

---

### 🗑️ Waste Tracker

Users can add waste records using:

* Date
* Category
* Weight
* Recycling status
* Description

Supported categories:

`Food` • `Plastic` • `Paper` • `Glass` • `Metal` • `E-waste` • `Battery Waste` • `Other`

<p align="center">
  <img src="screenshots/waste_tracker.png" width="850">
</p>

---

### 📊 Analytics

The Analytics section converts stored records into charts and statistics.

<p align="center">
  <img src="screenshots/analytics.png" width="850">
</p>

It helps users understand:

* Waste distribution
* High-waste categories
* Recycling activity
* Waste patterns

---

### 🧱 Material Flow

Material Flow provides a visual representation of waste categories and their movement through the waste-management process.

<p align="center">
  <img src="screenshots/material_flow.png" width="850">
</p>

---

### 🤖 AI Core

The **AI Core** provides the intelligent-analysis component of the application.

It is designed to work with available waste data and support sustainability-related recommendations.

<p align="center">
  <img src="screenshots/ai_core.png" width="850">
</p>

---

### 💡 Sustainability Recommendations

The application provides practical suggestions based on recorded waste information.

Recommendations can encourage:

* Better recycling habits
* Waste reduction
* Responsible disposal
* Greater environmental awareness

---

### 🌙 Dark & Light Mode

EcoMind AI supports both dark and light themes.

<p align="center">
  <img src="screenshots/dark_mode.png" width="410">
  <img src="screenshots/light_mode.png" width="410">
</p>

---

### 🔊 Voice Output

An optional voice-output feature provides **short notifications** when enabled.

The feature can be controlled from the application settings.

---

## ⚙️ How It Works

```text
                  USER
                    │
                    ▼
             Enter Waste Data
                    │
                    ▼
              Local Database
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      Analytics            AI Core
          │                   │
          ▼                   ▼
        Charts        Recommendations
          │                   │
          └─────────┬─────────┘
                    ▼
                Dashboard
```

---

## 🛠️ Technologies Used

| Technology       | Purpose                     |
| ---------------- | --------------------------- |
| Python           | Core application            |
| PyQt6            | Desktop graphical interface |
| SQLite           | Local data storage          |
| Matplotlib       | Charts and visualization    |
| AI / ML          | Intelligent analysis        |
| Python Libraries | Supporting functionality    |

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone YOUR_REPOSITORY_URL
```

### 2. Open the Project

```bash
cd EcoMind-AI
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python main.py
```

> Replace `main.py` with the actual entry-point filename if necessary.

---

## 📁 Project Structure

```text
EcoMind-AI/
│
├── main.py
├── requirements.txt
├── README.md
│
├── database/
│   └── waste_data.db
│
├── assets/
│   ├── images/
│   └── icons/
│
├── screenshots/
│   ├── dashboard.png
│   ├── waste_tracker.png
│   ├── analytics.png
│   ├── material_flow.png
│   ├── ai_core.png
│   ├── dark_mode.png
│   └── light_mode.png
│
└── docs/
    └── project_report.pdf
```

---

## 🧪 Example Workflow

```text
Add Waste
    ↓
Select Category
    ↓
Enter Weight
    ↓
Select Recycling Status
    ↓
Save Record
    ↓
Database Updated
    ↓
Statistics Updated
    ↓
Charts Updated
    ↓
AI Analysis & Recommendations
```

---

## 🔮 Future Scope

Future versions could include:

* Computer-vision waste classification
* Smart-bin integration
* IoT-based waste monitoring
* Advanced machine-learning models
* Mobile application
* Cloud synchronization
* Community-level waste analysis
* Waste-generation prediction

---

## ⚠️ Limitations

* Waste information depends on user-entered data.
* AI/ML functionality can be expanded with larger real-world datasets.
* The current application is primarily designed for desktop use.
* Recommendations depend on the available data.

---

## 👥 Team

### Cyber Guardians

**Project:** EcoMind AI — Intelligent Waste Management System

A student project combining **Python, AI/ML concepts, data visualization, and environmental awareness**.

---

## 🙏 Acknowledgements

We acknowledge the programming libraries, development tools, datasets, images, icons, and AI-assisted development resources used during development.

External resources are credited according to their respective licenses and usage requirements.

---

## 🌍 Vision

> **Track waste. Understand patterns. Build better habits.**

EcoMind AI aims to demonstrate how technology can make everyday waste management more measurable, understandable, and actionable.
