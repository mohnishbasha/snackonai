<img width="1536" height="1024" alt="ChatGPT Image Feb 3, 2026, 12_55_54 PM" src="https://github.com/user-attachments/assets/a605719a-77a3-4d10-be5c-a25c25388202" />

# BeeAI Framework: Building A Simple Weather Agent using AI 🌦️  
 
This project showcases how to build a **production-ready Weather AI Agent using the BeeAI Framework**. Unlike traditional chatbots, the agent follows a reasoning-first approach thinking step by step, determining when external data is needed, and responding intelligently rather than generating instant replies.

It accepts natural language weather queries, fetches live and forecast data through structured tools, and delivers concise, accurate, and well-structured answers. Powered by a local LLM, the agent runs fully offline, making it reliable, cost-effective, and suitable for real-world applications that require intelligent decision-making and real-time data access. Read more on our [Newsletter Website](https://www.snackonai.com/) 
<br/>

---
## 🧠 Technology Stack

### **[Ollama](https://ollama.com/download/windows)**
A lightweight tool that allows you to run large language models locally on your machine using simple terminal commands.

---

### **Granite 3.3 (8B)**
An open-source IBM large language model optimized for:
- Reasoning
- Tool usage
- Reliable, enterprise-grade AI workflows

---

### **[Python 3.10+](https://www.python.org/downloads/release/python-3100/)**
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
<br/>

---
## 🏗️ Project Architecture

The agent follows a **structured Reason + Act workflow**:
1. User submits a query
2. Agent reasons using `ThinkTool`
3. Agent decides whether external data is required
4. Weather data is fetched via `OpenMeteoTool`
5. A final, well-structured response is generated <br/>

<img width="728" height="858" alt="image" src="https://github.com/user-attachments/assets/8d02d7bf-6f3b-4fe7-812c-04de4895640c" />

---
## ⚙️ Setup and Implementation

- 1️⃣ Download the LLM Model

Run the following command to download the Granite 3.3 (8B) model locally:

```bash

ollama pull granite3.3:8b
```
This allows the agent to run fully offline without any API costs.<br/>

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


## 🤖 Agent Implementation

▶️ Running the Agent

- Execute the following command:
  
```bash 

python weather_agent.py

```
- You’ll see:
 ```bash

Enter your question:

```
- Example Queries
 ```bash

1. Give me the current weather in San Francisco.

2. Check temperature and humidity in Mumbai right now.

3. Show today’s sunrise and sunset weather for Kolkata.

```
 - Example Output 
 ```bash

Agent: The current weather in San Francisco is 9 degrees Celsius with a relative humidity of 81% and wind speeds of approximately 5.5 km/h.
