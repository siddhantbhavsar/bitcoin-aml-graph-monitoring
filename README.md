# 🪙 Bitcoin AML Transaction Monitoring System

An explainable **graph-based Anti-Money Laundering (AML) monitoring system for Bitcoin** built using the public Elliptic dataset.

This project demonstrates how real-world AML systems combine graph analytics, deterministic risk scoring, and LLM-assisted investigation summaries to generate analyst-ready alerts.

---

## 🚀 What This Project Does

This system simulates a production-style crypto AML pipeline:

1. Graph Feature Engineering  
   Extracts structural signals from Bitcoin transaction graphs (fan-in/out, exposure metrics).

2. Explainable Risk Scoring Engine  
   Assigns deterministic risk scores using bounded propagation and rule-based logic.

3. Alert Generation  
   Produces investigation-ready alerts with human-readable reasons.

4. LLM Investigator Copilot  
   Generates structured investigation summaries to assist compliance analysts.

The design prioritizes **explainability, auditability, and realistic AML workflows** over black-box prediction.

---

## 🏗 Architecture Overview

Elliptic Dataset  
↓  
Graph Feature Engineering  
↓  
Risk Scoring Engine  
↓  
Alert Generation  
↓  
LLM Investigator Copilot  
↓  
Analyst Investigation Output

---

## 📊 Dataset

Uses the **Elliptic Bitcoin Dataset (public research release)**:

- Transaction features
- Transaction graph edges
- Labeled illicit / non-illicit classes

Only core structural information is used for scoring to maintain explainability.

---

## 🧠 Key Concepts

- Graph-based behavioral signals
- Bounded risk propagation (1–2 hop exposure)
- Explainable alert reasoning
- Deterministic severity scoring
- Analyst-focused investigation outputs

---

## 🛠 Tech Stack

- Python
- Pandas
- NetworkX
- Jupyter notebooks
- OpenAI API (LLM investigation layer)

---

## ▶️ How to Run

Clone the repository:

git clone <repo-url>  
cd bitcoin-aml-monitoring  
pip install -r requirements.txt

Open the main notebook:

notebooks/aml_pipeline.ipynb

Run all cells to generate alerts and investigation summaries.

---

## 🎯 Why This Project Matters

Most AML research focuses on classification accuracy.  
This project focuses on **system design**:

- How alerts are generated in practice
- How risk is explained to investigators
- How AI supports — but does not replace — human review

It mirrors how modern fintech AML monitoring systems are architected.

---

## 📌 Future Extensions

- Real-time streaming pipeline
- Wallet/entity clustering
- Scalable graph processing
- Advanced investigation dashboards

---

## 📄 License

For research and educational purposes only.
