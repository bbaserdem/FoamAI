# 🧠 BrainLift: AI-First CFD Assistant for OpenFOAM

## 1. Problem

CFD is extremely difficult for non-experts to access.  
Even though the value of fluid simulations is high across domains  
(e.g. environmental science, automotive design, architecture),  
the **only viable open-source tool—OpenFOAM—is extremely technical**  
and difficult to install, configure, or use without an engineering PhD.

## 2. Constraints

- **Accessibility**: Must work for users without deep technical expertise  
- **Setup**: Should minimize installation friction; ideally runs in the cloud  
- **Timeline**: We aim to deliver an MVP in **one week**  
- **Performance**: Speed is not critical; we will only support **simple test cases**  
- **Compute**: We use an AWS instance like `c7i.2xlarge`, optimized for general computing

## 3. Idea

An **AI-powered, human-in-the-loop OpenFOAM Assistant** that guides users through the CFD pipeline.  
It automates config generation, parameter tuning, and job submission using LLMs.  
**Users remain in control** at every step: the system makes suggestions, explains options, and responds to feedback.  
User provides a natural language problem description  
(e.g. “simulate wind flow over a building”),  
and the assistant helps build the necessary mesh, config files, and solver steps via OpenFOAM behind the scenes.  
The system is deployed via **Terraform + Docker** to simplify infrastructure setup,  
with all logic callable via APIs.

## 4. Why It's AI-First

AI is not bolted on—it's **the primary interface**.  
We use LLMs to:  
- Parse user intent from natural language  
- Generate and explain OpenFOAM configuration files  
- Guide users step-by-step while allowing edits and overrides  

This is what enables **non-experts** to access a traditionally expert-only domain,  
while keeping **human judgment in the loop**.

---

## Supporting Sections

### 🩻 Symptoms

- Users don’t know how to set up meshes, solvers, or boundary conditions  
- OpenFOAM setup on local machines is extremely fragile and niche  
- Documentation is too technical or fragmented

### 🧬 Root Causes

- OpenFOAM was built for expert users with CLI experience  
- The simulation workflow is non-linear and error-prone  
- There is no universal GUI or assistant workflow for beginners

### ✅ Success Criteria

- User can go from description → result image without editing raw OpenFOAM config  
- No need for local installation  
- Simulations work for simple canonical cases (e.g. airflow, pressure over an object)  
- System handles full pipeline: parse → setup → run → visualize  
- Users can inspect and modify every step in the workflow

### 🧠 Existing Alternatives

- [OpenFOAM Assistant GPT](https://chatgpt.com/g/g-1eg3gAcQV-openfoam-assistant): helps with parameter selection, but does not run simulations  
- Research (e.g. [AutoCFD](https://arxiv.org/pdf/2504.19338), [ICCS 2021](https://www.iccs-meeting.org/archive/iccs2021/papers/127430361.pdf)): promising AI approaches, but no usable product  
- Reddit/Discord: ad hoc human support, no structured tools

