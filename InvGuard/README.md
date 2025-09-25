
## Project Overview

The framework consists of two main flows:

1. **Flow 1: Invariant Generation and Verification**
   - Automatically generates invariants for smart contracts using AI models
   - Verifies the generated invariants using Z3 theorem prover
   - Refines invariants through iterative analysis

2. **Flow 2: Exploit Analysis and Fix Generation**
   - Analyzes smart contracts for potential vulnerabilities
   - Generates detailed exploit analysis reports
   - Creates secure contract fixes based on verified invariants

## Prerequisites

- Python 3.8+
- OpenAI API key (for AI model access)

## Setup Instructions

1. Install the required dependencies in requirements.txt .

2. Configure the environment variables:
   - Set your OpenAI API key in both `flow_1_files/agent.py` and `flow_2_files/agent.py`
   - Configure the base execution directory paths as specified in the configuration section

## Prepare input contracts:

Place your Solidity .sol files in the contracts/ directory.

## Usage

### Flow 1: Invariant Generation

1. Navigate to the flow 1 directory:
   ```bash
   cd flow_1_files
   ```

2. Run the agent:
   ```bash
   python agent.py
   ```

3. Before running, ensure you:
   - Add your OpenAI API key in `agent.py`
   - Configure the following paths:
     - `BASE_EXECUTION_DIR`: Base directory for execution
     - `CORRECT_INVARIANTS_DIR`: Directory for storing verified invariants

### Flow 2: Exploit Analysis

1. Navigate to the flow 2 directory:
   ```bash
   cd flow_2_files
   ```

2. Run the agent:
   ```bash
   python agent.py
   ```

3. Before running, ensure you:
   - Add your OpenAI API key in `agent.py`
   - Configure the `BASE_EXECUTION_DIR` path
   -

## Project Structure

```
flow_1_files/
├── agent.py          # Main agent for invariant generation
├── tools.py          # Utility functions
├── z3_checker.py     # Z3 verification implementation
└── invariant_autogen.py  # Invariant generation logic

flow_2_files/
├── agent.py          # Main agent for exploit analysis
```
Fine-tuning dataset: available in the repository root at ft/

## Configuration

The following configurations need to be set in both flow's agent.py files:

- `OPENAI_API_KEY`: Your OpenAI API key
- `BASE_EXECUTION_DIR`: Base directory for execution
- `CORRECT_INVARIANTS_DIR`: Directory for storing verified invariants (Flow 1 only)
- `MAX_REFINEMENT_ITERATIONS`: Maximum number of refinement iterations (Flow 1 only)

