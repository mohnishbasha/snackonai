# BeeAI Weather Agent 🌦️  
*A Step-by-Step Guide to Building a Reasoning-Based Weather Agent using BeeAI Framework*

This project demonstrates how to build a **production-ready Weather AI Agent** using the **BeeAI Framework**.  
Unlike traditional chatbots, this agent reasons step by step, decides when external data is required, and fetches **real-time weather information** using structured tools.

---

## 🚀 What This Project Does

- Accepts natural language weather queries
- Thinks before responding using a reasoning-first approach
- Fetches live and forecast weather data
- Runs fully **offline** using a local LLM
- Produces concise, accurate, and structured answers

---

## 🧠 Technology Stack

### **Ollama**
A lightweight tool that allows you to run large language models locally on your machine using simple terminal commands.

---

### **Granite 3.3 (8B)**
An open-source IBM large language model optimized for:
- Reasoning
- Tool usage
- Reliable, enterprise-grade AI workflows

---

### **Python 3.10+**
A modern Python runtime required for compatibility with the BeeAI Framework.

---

### **OpenMeteoTool**
A BeeAI-integrated tool that enables the agent to fetch **real-time and forecast weather data** from the Open-Meteo API.

---

### **ThinkTool**
Forces the agent to pause, reason, and plan before responding.  
This ensures the agent:
- Understands what it already knows
- Identifies missing information
- Chooses the correct tool instead of guessing

---

## 🏗️ Project Architecture

The agent follows a **structured Reason + Act workflow**:
1. User submits a query
2. Agent reasons using `ThinkTool`
3. Agent decides whether external data is required
4. Weather data is fetched via `OpenMeteoTool`
5. A final, well-structured response is generated

---

## ⚙️ Setup and Implementation

-gi 1️⃣ Download the LLM Model

Run the following command to download the Granite 3.3 (8B) model locally:

```bash

ollama pull granite3.3:8b
```
-This allows the agent to run fully offline without any API costs.

- 2️⃣ Create Project Directory
 ```bash
 
    mkdir beeai-python-demo
    cd beeai-python-demo

```
- 3️⃣ Create and Activate Virtual Environment
 ```bash

    python -m venv venv

```
- Activate it:

- Windows
 ```bash

venv\Scripts\activate

```
- Mac / Linux
 ```bash

source venv/bin/activate

```
- 4️⃣ Install Dependencies\
```bash 

    pip install beeai-framework

```
# 🤖 Agent Implementation

- The weather_agent.py file creates an intelligent BeeAI agent that:

- Uses ThinkTool to reason before answering

- Uses OpenMeteoTool for live weather data

- Enforces structured behavior using RequirementAgent

- Tracks tool interactions for observability



#▶️ Running the Agent

- Execute the following command:
```bash 

python weather_agent.py

```
- You’ll see:
 ```bash

Enter your question:

```
- 💬 Example Queries
 ```bash

1. Give me the current weather in San Francisco.

2. Check temperature and humidity in Mumbai right now.

3. Show today’s sunrise and sunset weather for Kolkata.

```
 - Example Output 
 ```bash

Agent: The current weather in San Francisco is 9 degrees Celsius with a relative humidity of 81% and wind speeds of approximately 5.5 km/h.

```
 ✅ Key Takeaways

- This is not a simple chatbot — it’s a reasoning-based AI agent

- The agent is forced to think before responding

- Tool usage is explicit and traceable

The system is predictable, auditable, and production-ready
```bash
