# 🌱 EcoMind AI

### Intelligent Waste Management & Recycling System

<p align="center">
  <b>Turning everyday waste records into meaningful sustainability insights.</b>
</p>

<p align="center">
  <img src="screenshots/dashboard.png" width="900">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?style=for-the-badge&logo=python">
  <img src="https://img.shields.io/badge/PyQt6-GUI-green?style=for-the-badge">
  <img src="https://img.shields.io/badge/SQLite-Database-orange?style=for-the-badge&logo=sqlite">
  <img src="https://img.shields.io/badge/SDG-11%20%7C%2012%20%7C%2013-brightgreen?style=for-the-badge">
</p>

---

## 📌 About The Project

**EcoMind AI** is a Python-based desktop application designed to help households and communities **record, understand, and improve their waste-management habits**.

Instead of treating waste as something that is simply thrown away, EcoMind AI turns waste records into structured information that can be analyzed.

The system allows users to:

* Record waste by category
* Track recycled and non-recycled material
* View category-wise waste statistics
* Monitor recycling performance
* Identify high-waste categories
* Visualize waste data through charts
* View material movement through the Material Flow interface
* Generate sustainability-focused recommendations
* Maintain waste records using a local database

> **The goal is simple: Measure waste → Understand waste → Reduce waste.**

---

# 🌍 Why EcoMind AI?

Waste management becomes difficult when people cannot clearly see **where their waste is coming from** or **how much of it is actually being recycled**.

A simple list of waste records is not enough.

EcoMind AI provides a visual and structured way to answer questions such as:

**What type of waste do we produce the most?**

**How much of our waste is recycled?**

**Which categories need more attention?**

**How can our waste habits be improved?**

This transforms raw waste records into information that can support better everyday decisions.

---

# 🎯 Objectives

The main objectives of EcoMind AI are:

* ♻️ Encourage responsible waste management
* 📊 Convert waste records into useful statistics
* 🗂️ Maintain organized waste records
* 📈 Track recycling performance
* 🔎 Identify high-waste categories
* 💡 Provide practical sustainability recommendations
* 🌱 Promote environmentally responsible habits
* 💻 Demonstrate Python fundamentals and Object-Oriented Programming

---

# 🌱 Sustainable Development Goals

EcoMind AI supports three major United Nations Sustainable Development Goals.

### 🏙️ SDG 11 — Sustainable Cities and Communities

Encourages better waste-management practices within households and communities.

### ♻️ SDG 12 — Responsible Consumption and Production

Helps users understand their consumption and disposal patterns while encouraging recycling and waste reduction.

### 🌍 SDG 13 — Climate Action

Better waste management can contribute to reducing environmental impact and promoting more sustainable lifestyles.

<p align="center">
  <b>SDG 11 · SDG 12 · SDG 13</b>
</p>

---

# ✨ Key Features

## 📊 Waste Dashboard

The dashboard provides a quick overview of the current waste situation.

It can display important indicators such as:

* Total waste
* Recycled waste
* Recycling rate
* Highest waste category
* Waste reduction information
* Overall waste statistics

The purpose is to make important information visible **without requiring the user to inspect every record manually**.

---

## 🗂️ Waste Record Management

Users can maintain individual waste records with information such as:

* Date
* Waste category
* Weight
* Recycling status
* Description

Supported categories include:

`Food` · `Plastic` · `Paper` · `Glass` · `Metal` · `E-waste` · `Other`

The system is designed around structured records rather than unorganized text.

---

# ♻️ Recycling Tracking

EcoMind AI separates recycled and non-recycled waste so that recycling performance can be measured.

The recycling rate is calculated from the recorded waste data, allowing users to monitor whether their recycling practices are improving.

---

# 📈 Data Visualization

Raw numbers can be difficult to understand.

EcoMind AI therefore uses visual analytics to make waste patterns easier to interpret.

Examples include:

* Category distribution
* Recycling statistics
* Waste trends
* Comparative charts

<p align="center">
  <img src="screenshots/charts.png" width="850">
</p>

> **Visualization turns a table of numbers into a pattern that people can understand.**

---

# 🔄 Material Flow

One of the key visual components of EcoMind AI is the **Material Flow**.

It provides a visual representation of how different waste materials move through the waste-management process.

<p align="center">
  <img src="screenshots/material_flow.png" width="850">
</p>

The flow helps communicate the idea that waste does not necessarily have to end at disposal.

Depending on the material, it can move toward processes such as:

**Collection → Sorting → Recycling / Recovery → Responsible Disposal**

This makes the environmental purpose of the application easier to understand during a demonstration.

---

# 🧠 Intelligent Data Analysis

EcoMind AI focuses on using the recorded data to provide meaningful analysis rather than simply storing numbers.

The system can analyze waste records to identify patterns such as:

* High-waste categories
* Recycling performance
* Category distribution
* Waste quantities
* Areas requiring improvement

Recommendations are based on the information available in the recorded dataset.

> **Important:** The README describes only the intelligence and analysis actually implemented in the submitted source code. It does not claim unsupported external AI services or advanced models.

---

# 🏗️ Object-Oriented Programming

OOP is an important part of the project architecture.

The system is organized around objects representing major concepts of the application.

Examples include:

### `User / Household`

Represents the household or user using the waste-management system.

### `WasteRecord`

Represents an individual waste entry.

A waste record can contain information such as:

```text
Date
Category
Weight
Recycling Status
Description
```

### Why OOP?

Using classes helps keep the application:

* Organized
* Modular
* Easier to maintain
* Easier to extend
* Closer to real-world entities

This also demonstrates the competition requirement of applying **Python fundamentals and Object-Oriented Programming**.

---

# 🗄️ Database

EcoMind AI uses **SQLite** for local data persistence.

Instead of losing records when the application closes, waste information can be stored locally and retrieved later.

The database supports the application's core workflow:

```text
User Input
     ↓
Waste Record
     ↓
SQLite Database
     ↓
Data Processing
     ↓
Statistics & Visualization
     ↓
Recommendations
```

---

# 🔄 Application Workflow

<p align="center">
  <b>Record → Store → Process → Analyze → Visualize → Improve</b>
</p>

### 1. Record

The user enters waste information.

### 2. Store

The information is saved in the local database.

### 3. Process

The application processes the recorded values.

### 4. Analyze

Statistics and category-level information are calculated.

### 5. Visualize

Charts and dashboard components present the results.

### 6. Improve

The system highlights areas where better waste-management practices can be applied.

---

# 🖥️ User Interface

EcoMind AI uses a modern desktop dashboard designed to make environmental data easier to understand.

The interface follows a:

* Dark futuristic theme
* Clean dashboard layout
* Green and cyan sustainability-focused accents
* Card-based information display
* Visual charts
* Navigation-based structure

The design is intended to feel **modern and technological without looking like a hacker interface**.

---

# 🛠️ Technologies Used

| Tec
