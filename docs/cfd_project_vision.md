# CFD Project Vision & Architecture

## Project Vision & Goals

**The core goal is to make computational fluid dynamics (CFD) more accessible** by creating an intelligent application that allows users to set up and run fluid dynamics simulations using natural language.

The project aims to serve two main user profiles:

1. **Technical Users / Admins:** Who can set up the entire backend infrastructure in their own cloud account.
2. **End-Users / Clients:** Who interact with a simple desktop application to run simulations without needing any knowledge of the underlying setup.

## High-Level Architecture (MVP)

For the Minimum Viable Product (MVP), we've settled on a **hybrid client-server model** to prioritize simplicity and speed of development.

### 1. The Backend: A Single Cloud VM ☁️

* **Hosting:** Runs on a commercial cloud platform (like AWS, GCP, or Azure) within the technical user's own account.
* **Provisioning:** The technical user will deploy this VM using **Infrastructure as Code** scripts (likely **Terraform**) that you provide.
* **Software Stack:** This single VM will host:
  * **OpenFOAM:** To perform the core CFD calculations.
  * **ParaView Server** (`pvserver`): To handle the heavy-lifting of data processing and 3D rendering for visualization.
  * **Our Application's Backend Logic:** A lightweight API server (e.g., Python with FastAPI) that receives requests from the desktop client, interfaces with an LLM, and orchestrates the OpenFOAM and ParaView processes.

### 2. The Frontend: A Hybrid Desktop Application ��️

* **Technology:** A user-friendly desktop application built with a standard GUI framework like **Python with Qt**.
* **Functionality:**
  * Provides the chat interface for the user to describe their simulation to an LLM.
  * Communicates with the cloud backend to send job requests and receive status updates.
  * Launches and embeds a native **ParaView client window**, which connects directly to the `pvserver` on the cloud VM for high-performance, interactive visualization.

This architecture ensures that the end-user experience is simple, while the powerful computational work is handled efficiently in the cloud.
