
# Razorpay IntentGuard

> **Real-Time Semantic Intent Verification Proxy & Policy Enforcement Gateway for Agentic Commerce**

[![Razorpay API](https://img.shields.io/badge/Razorpay-v1%2Forders-blue)](https://razorpay.com)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688)](https://fastapi.tiangolo.com)
[![Gemini API](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-orange)](https://ai.google.dev)
[![Security](https://img.shields.io/badge/Security-HMAC%20SHA--256-red)](https://en.wikipedia.org/wiki/HMAC)

---

## Executive Summary

Autonomous AI shopping agents frequently make purchases on behalf of consumers. However, standard payment gateway rails only enforce flat spending caps (e.g., total price ≤ ₹70,000). Existing payment networks cannot evaluate natural language constraints or inspect individual cart line items to verify if a transaction actually aligns with the user's original instructions.

**Razorpay IntentGuard** acts as an intelligent pre-authorization gateway proxy sitting in front of Razorpay's `POST /v1/orders` API. It dynamically compiles natural language user instructions into cryptographically signed JSON policy envelopes, inspects cart line items for sneaky merchant upsells or unauthorized accessories, and introduces an asynchronous **Human-in-the-Loop (HOLD)** state machine for ambiguous overages[cite: 2, 4, 6].

---

## Architecture & Protocol Alignment

Razorpay IntentGuard aligns global standards like **Google AP2 (Intent/Cart Mandates)**[cite: 4, 5, 6] and **Mastercard Verifiable Intent Frameworks** directly with the Razorpay API ecosystem[cite: 2, 4, 6].

```
┌─────────────────────────┐
│ User Intent Prompt      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Gemini LLM              │
│ Intent Compiler         │
└───────────┬─────────────┘
            │ Generates HMAC Policy
            ▼
┌─────────────────────────┐      Checkout Payload      ┌─────────────────────────┐
│ Signed Policy Envelope  │ ─────────────────────────> │ Razorpay IntentGuard    │
└─────────────────────────┘                            │ Proxy Interceptor       │
                                                       └───────────┬─────────────┘
                                                                   │
                                   ┌───────────────────────────────┼───────────────────────────────┐
                                   │                               │                               │
                                   ▼                               ▼                               ▼
                      ┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
                      │ STATUS: APPROVED        │     │ STATUS: BLOCKED         │     │ STATUS: HOLD            │
                      ├─────────────────────────┤     ├─────────────────────────┤     ├─────────────────────────┤
                      │ Executes Razorpay Order │     │ Prevents Order Creation │     │ Dispatches WhatsApp     │
                      │ (POST /v1/orders)       │     │ Logs Intent Violation   │     │ Interactive Link        │
                      └─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘

```
Key Features
Natural Language Intent Compiler: Converts unstructured prompts into strict JSON policy bounds (budget limits, required categories, prohibited categories, and negative keywords) using Gemini 1.5 Flash[cite: 2, 4, 6].

Cryptographic Non-Repudiation: Signs compiled policies using HMAC SHA-256 to prevent payload tampering during multi-step agent shopping sessions[cite: 2, 4, 6].

Semantic Line-Item Inspection: Evaluates individual item titles/categories against negative constraints (e.g., blocking ₹9,000 extended warranties even if total cart price remains under budget)[cite: 2, 4, 6].

Human-in-the-Loop (HITL) State Machine: Ambiguous transactions (e.g., 2% over budget within a 5% tolerance window) trigger a HOLD state, sending interactive WhatsApp approval links to the user before resuming order creation.

Containerized Microservice: Built and deployed using Docker for simple local setup and production environment parity.
Tech Stack & Directory Structure
Tech Stack
Proxy Gateway: Python 3.11, FastAPI, Uvicorn[cite: 2, 4, 6]

Intent Compiler: Google GenAI SDK (gemini-1.5-flash)[cite: 2, 4, 6]

Validation Engine: Pydantic v2, Hashlib (HMAC SHA-256)[cite: 2, 4, 6]

Payment Gateway Integration: Official Razorpay Python SDK (razorpay)

Escalation Service: Twilio SDK (WhatsApp Outbound Webhooks)

Containerization: Docker & Docker Compose


razorpay-intentguard/
├── apps/
│   ├── proxy/
│   │   ├── app/
│   │   │   ├── api/          # Interceptor & Escalation Routes
│   │   │   ├── compiler/     # Gemini Intent Engine & HMAC Signer
│   │   │   ├── evaluator/    # Semantic Rule Pipeline
│   │   │   ├── services/     # Escalation Store & WhatsApp Notifier
│   │   │   └── main.py
│   │   └── Dockerfile
│   └── dashboard/            # Agent Simulator & Audit UI
├── docker-compose.yml
└── README.md


Quick Start & Deployment Guide1. Prerequisites & Environment SetupCreate an .env file in apps/proxy/.env (or root):BashGEMINI_API_KEY="your-gemini-api-key"
RAZORPAY_KEY_ID="rzp_test_xxxxxxxxxxxx"
RAZORPAY_KEY_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"
POLICY_HMAC_SECRET="super-secret-hmac-key"
2. Launch Containerized Proxy BackendBuild and run the stack using Docker Compose:Bashdocker-compose up --build -d
3. Verify Proxy HealthHealth Check Endpoint: http://localhost:8000/healthSwagger API Docs: http://localhost:8000/docs4. Run Automated Test SuiteBashpython apps/proxy/test_hitl.py
Verified Gateway PathwaysScenarioInput PromptCart ContentsProxy ResultGateway ActionClean Match"Buy laptop under ₹30,000"Laptop (₹28,500)200 APPROVEDExecutes razorpay.Client.order.create()Category Violation"Buy laptop under ₹70,000, no warranty"Laptop (₹65k) + Warranty (₹9k)400 BLOCKEDPrevents checkout; Logs violation reasonHITL Overage"Buy laptop under ₹70,000"Upgraded Laptop (₹71,400 - 2% over)200 HOLDDispatches approval webhook; Resumes on clickAPI ReferenceGET /health — Service health checkPOST /v1/orders — Interceptor endpoint evaluating cart payloads against signed intent policiesPOST /v1/escalations/{escalation_id}/decision — Decision endpoint for human approval callbackGET /v1/audit-trail — Fetches transaction audit logs
