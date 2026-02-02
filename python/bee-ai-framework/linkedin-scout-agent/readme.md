# LinkedIn Scout Agent 🤖🔍  
**Building a Custom Agent with BeeAI Framework**

In our previous blog, **BeeAI Framework: Building a Simple Weather Agent**, we explored the foundations of agentic workflows and built our first BeeAI agents using pre-built tools. We discussed why the industry is moving beyond simple chatbots toward intelligent, autonomous agents that can reason, plan, and act with intent rather than merely generating text.

In this project, we take the next step.

Instead of relying on pre-packaged capabilities, we build **custom intelligence** by creating a **LinkedIn Scout Agent** using the BeeAI Framework. This agent is designed to solve a real-world problem faced by job seekers, founders, and sales professionals:  
**finding real hiring managers and decision-makers on LinkedIn based on role, industry, and location.**

---

## 🚀 What This Agent Does

- Searches LinkedIn profiles using advanced Google dorking
- Identifies real hiring managers, founders, or decision-makers
- Reasons before acting to ensure accurate and targeted results
- Uses structured schemas for safe, predictable tool execution
- Enforces limits to prevent uncontrolled API usage

This is not a chatbot — it’s a **purpose-built, reasoning-driven agent**.

---

## 🧠 Technology Stack

### Ollama
A lightweight runtime that allows you to run large language models locally using simple terminal commands.

### IBM Granite 3.3 (8B)
A native open-source large language model optimized for:
- Reasoning
- Tool usage
- Enterprise-grade reliability

### Python 3.10+
Required runtime version for compatibility and modern async workflows.

### SerpAPI (Custom Tool Integration)
Used to perform advanced Google searches (Google Dorking) to discover LinkedIn profiles and real decision-makers.

### ThinkTool
Forces the agent to pause, reason, and plan before responding — ensuring step-by-step thinking instead of rushed or random answers.

---

## 🧩 Agentic Workflow

The agent follows a structured execution flow:
1. Understand the user intent
2. Think and plan using `ThinkTool`
3. Decide whether external data is required
4. Execute a controlled search via SerpAPI
5. Return clean, structured results

This architecture ensures predictability, safety, and explainability.

---

## ⚙️ Setup and Implementation

### 1️⃣ Download the LLM Model

```bash
ollama pull granite3.3:8b

```
### 2️⃣ Create Project Directory
```bash

mkdir beeai_custom_agent
cd beeai_custom_agent

```
### 3️⃣ Create and Activate Virtual Environment
```bash

python -m venv venv

```
- Activate it:

- Windows
```bash 

venv\Scripts\activate

```
Mac/Linux
```bash

source venv/bin/activate

```
### 4️⃣ Install Dependencies
```bash

pip install beeai-framework requests
pip install pydantic

```
###🧠 Agent Implementation
```bash 

linkedin-scout-agent.py
 
```
#### This agent:

- Uses Pydantic schemas to define strict input contracts

- Implements a custom SerpAPI tool

- Enforces reasoning before action using ThinkTool

- Limits API calls to prevent misuse

- Tracks tool execution for observability

### ▶️ Running the Agent
- Update the following line with your SerpAPI key:
```bash

SERP_API_KEY = "YOUR_SERP_API_KEY"

```
Run the agent:
```bash

python linkedin_scout_agent.py

```
🧪 Example Query
```bash

query = "Find 2 Hiring Managers for Android Development in San Francisco, California."

```
📤 Example Output
```bash

--- Agent Response ---

1. Name: Sarah Lee  
   LinkedIn: https://www.linkedin.com/in/sarahleeandroid/  
   Position: Senior Android Developer & Hiring Manager  
   Location: San Francisco, California

2. Name: John Smith  
   LinkedIn: https://www.linkedin.com/in/john-smith-android/  
   Position: Android Development Lead & Hiring Manager  
   Location: San Francisco, California

```
## 🔍 Design Logic Behind the Agent

### Clear Input Contracts

Pydantic schemas ensure the agent knows exactly what data each tool requires, removing ambiguity and improving API accuracy.

### Thoughtful Tool Architecture

####Custom tools include:

- Explicit input schemas
- Built-in observability
- Non-blocking async execution

### Protection & Safety

- Usage limits prevent uncontrolled API calls, protecting real-world budgets and system stability.

### Reasoning Before Action

- By enforcing ThinkTool, the agent plans before executing searches — resulting in higher-quality, targeted outputs.

### ✅ Key Takeaways

- This project moves beyond theory into real-world agentic AI

- The agent doesn’t just chat — it acts with intent

- BeeAI enables structured reasoning, safe tool usage, and production-ready safeguards

- Demonstrates how agents can solve practical problems, not demos