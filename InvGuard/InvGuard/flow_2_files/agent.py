import asyncio
import os
import logging
from agents import Agent, Runner, agent, set_tracing_export_api_key, handoff, trace
from openai import OpenAI
from agents.extensions import handoff_filters
from dataclasses import dataclass, field
from agents import ModelSettings 

import time
import sys
from dataclasses import dataclass, field

from agents import Agent, Runner, function_tool, handoff, ModelSettings
from openai import OpenAI


os.environ["OPENAI_API_KEY"] = "<your-api-key>" 

client = OpenAI()
model_1 = "<fine-tuned-model>"
model_2 = "<model-name>"


BASE_EXECUTION_DIR = "<add-base-execution-dir>"

@function_tool
def save_exploit_analysis(contract_code: str, vulnerabilities: str, exploit_details: str) -> str:
    """
    Saves the exploit analysis results.
    Args:
        contract_code: The original smart contract code.
        vulnerabilities: Description of found vulnerabilities.
        exploit_details: Detailed exploit information.
    Returns:
        File path where analysis was saved.
    """
    exploits_dir = os.path.join(BASE_EXECUTION_DIR, "exploit_analysis")
    os.makedirs(exploits_dir, exist_ok=True)
    
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    filename = f"exploit_analysis_{timestamp}.txt"
    filepath = os.path.join(exploits_dir, filename)
    
    try:
        with open(filepath, "w", encoding='utf-8') as f:
            f.write(f"Exploit Analysis Report\n")
            f.write(f"Generated At: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("ORIGINAL CONTRACT CODE\n")
            f.write("=" * 80 + "\n")
            f.write(f"{contract_code}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("VULNERABILITIES FOUND\n")
            f.write("=" * 80 + "\n")
            f.write(f"{vulnerabilities}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("EXPLOIT DETAILS\n")
            f.write("=" * 80 + "\n")
            f.write(f"{exploit_details}\n")
        
        logging.info(f"Exploit analysis saved to {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"Error saving exploit analysis: {e}")
        return f"Error: {e}"

@function_tool
def save_final_fix(original_contract: str, fixed_contract: str, fix_description: str, invariants_used: str) -> str:
    """
    Saves the final approved fix.
    Args:
        original_contract: The original vulnerable contract code.
        fixed_contract: The fixed contract code.
        fix_description: Description of the fix applied.
        invariants_used: Invariants that were considered/used.
    Returns:
        File path where fix was saved.
    """
    fixes_dir = os.path.join(BASE_EXECUTION_DIR, "approved_fixes")
    os.makedirs(fixes_dir, exist_ok=True)
    
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    filename = f"approved_fix_{timestamp}.txt"
    filepath = os.path.join(fixes_dir, filename)
    
    try:
        with open(filepath, "w", encoding='utf-8') as f:
            f.write(f"Approved Smart Contract Fix\n")
            f.write(f"Generated At: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("FIX DESCRIPTION\n")
            f.write("=" * 80 + "\n")
            f.write(f"{fix_description}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("INVARIANTS CONSIDERED\n")
            f.write("=" * 80 + "\n")
            f.write(f"{invariants_used}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("ORIGINAL CONTRACT\n")
            f.write("=" * 80 + "\n")
            f.write(f"{original_contract}\n\n")
            
            f.write("=" * 80 + "\n")
            f.write("FIXED CONTRACT\n")
            f.write("=" * 80 + "\n")
            f.write(f"{fixed_contract}\n")
        
        logging.info(f"Final fix saved to {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"Error saving final fix: {e}")
        return f"Error: {e}"


@dataclass
class AgentContext:
    user_query: str
    contract_code: str = ""
    invariants_file_path: str = ""
    exploit_analysis_path: str = ""



attack_module_agent = Agent[AgentContext](
    name="attack_module_agent",
    instructions="""You are the Attack Module Agent - a security expert that analyzes smart contracts for vulnerabilities.

**Your Task:**
1. **Analyze the provided smart contract code** for security vulnerabilities
2. **Identify specific attack vectors** such as:
   - Reentrancy attacks
   - Integer overflow/underflow
   - Access control issues
   - Randomness manipulation
   - Front-running vulnerabilities
   - Logic flaws

3. **Generate detailed exploit information** including:
   - Step-by-step attack scenarios
   - Potential impact assessment
   - Code locations where vulnerabilities exist

4. **Save your analysis** using the `save_exploit_analysis` tool with:
   - `contract_code`: The original contract
   - `vulnerabilities`: List and description of vulnerabilities found
   - `exploit_details`: Detailed exploit scenarios and attack vectors

5. **Hand off to Fix Maker** using `fix_maker_agent_handoff` with your analysis results

Focus on providing actionable vulnerability information that can be used to create effective fixes.
""",
    model=model_1,
    tools=[save_exploit_analysis],
    handoffs=[]
)

fix_maker_agent = Agent[AgentContext](
    name="fix_maker_agent",
    instructions="""You are the Fix Maker Agent - a smart contract security expert specializing in vulnerability remediation.

**Your Inputs:**
- Exploit analysis from the Attack Module
- Original contract code
- Invariants summary file (if available)

**Your Task:**
1. **Review the exploit analysis** and understand all identified vulnerabilities
2. **Read and consider the invariants** from the invariants summary file to ensure your fix maintains contract properties
3. **Generate a comprehensive fix** that addresses all vulnerabilities while:
   - Maintaining contract functionality
   - Preserving intended business logic
   - Following security best practices
   - Respecting the invariants

4. **Create fixed contract code** with clear comments explaining the changes
5. **Hand off to Fix Checker** using `fix_checker_agent_handoff` with:
   - Your proposed fix
   - Explanation of changes made
   - How the fix addresses each vulnerability

**Fix Quality Guidelines:**
- Address root causes, not just symptoms
- Minimize code changes while maximizing security
- Ensure backward compatibility where possible
- Add appropriate access controls and validations
- Consider gas efficiency
""",
    model=model_1,
    tools=[],
    handoffs=[]
)

fix_checker_agent = Agent[AgentContext](
    name="fix_checker_agent",
    instructions="""You are the Fix Checker Agent - a senior security auditor who validates proposed fixes.

**Your Task:**
1. **Review the proposed fix** from the Fix Maker
2. **Verify the fix addresses all vulnerabilities** identified in the original exploit analysis
3. **Check that invariants are preserved** by reviewing the invariants summary
4. **Validate the fix quality** by checking:
   - All attack vectors are properly mitigated
   - No new vulnerabilities are introduced
   - Contract functionality is preserved
   - Code quality and clarity
   - Gas efficiency considerations

**Decision Making:**
- **If the fix is satisfactory:**
  - Call `save_final_fix` tool with the approved fix details
  - End the workflow with approval confirmation

- **If the fix needs improvement:**
  - Provide specific feedback on what needs to be changed
  - Hand back to `fix_maker_agent_handoff` with detailed improvement requests
  - Continue the loop until a satisfactory fix is achieved

**Approval Criteria:**
- All identified vulnerabilities are properly addressed
- No new security issues are introduced
- Contract maintains its intended functionality
- Code changes are minimal and clear
- Fix respects the contract's invariants
""",
    model=model_1,
    tools=[save_final_fix],
    handoffs=[]
)

orchestrator_agent = Agent[AgentContext](
    name="orchestrator_agent",
    instructions="""You are the Orchestrator Agent for the smart contract fix generation workflow.

**Your Role:**
1. **Parse the user input** to extract:
   - Smart contract code to be analyzed
   - Path to invariants summary file (if provided)

2. **Initialize the workflow** by handing off to the Attack Module Agent
3. **Set up the context** with the contract code and invariants file path

Simply extract the necessary information and start the attack analysis process.
""",
    model=model_2,
    tools=[],
    handoffs=[]
)


attack_module_agent_handoff = handoff(
    agent=attack_module_agent,
    tool_name_override="attack_module_agent_handoff",
    tool_description_override="Initiates security analysis of the smart contract to identify vulnerabilities and generate exploit details."
)

fix_maker_agent_handoff = handoff(
    agent=fix_maker_agent,
    tool_name_override="fix_maker_agent_handoff",
    tool_description_override="Requests the Fix Maker to generate fixes based on exploit analysis and invariants. Provide exploit details and contract information."
)

fix_checker_agent_handoff = handoff(
    agent=fix_checker_agent,
    tool_name_override="fix_checker_agent_handoff",
    tool_description_override="Requests the Fix Checker to validate proposed fixes. Provide the proposed fix and explanation for review."
)


orchestrator_agent.handoffs = [attack_module_agent_handoff]
attack_module_agent.handoffs = [fix_maker_agent_handoff]
fix_maker_agent.handoffs = [fix_checker_agent_handoff]
fix_checker_agent.handoffs = [fix_maker_agent_handoff]  


orchestrator_agent.model_settings = ModelSettings(tool_choice="auto")
attack_module_agent.model_settings = ModelSettings(tool_choice="auto")
fix_maker_agent.model_settings = ModelSettings(tool_choice="auto")
fix_checker_agent.model_settings = ModelSettings(tool_choice="auto")

async def main():
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    
    user_query = """
Please analyze and fix the following smart contract. 

Invariants file: <path to invariants summary file>

<solidity code>

</solidity code>

"""

    print("Starting smart contract fix generation workflow...")
    os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
    print(f"Results will be saved in: {BASE_EXECUTION_DIR}/")

    lines = user_query.strip().split('\n')
    invariants_path = ""
    contract_code = user_query 
    
    for line in lines:
        if line.startswith("Invariants file:"):
            invariants_path = line.split(":", 1)[1].strip()
            break

    agent_run_context = AgentContext(
        user_query=user_query,
        contract_code=contract_code,
        invariants_file_path=invariants_path
    )

    try:
        run_outcome = await Runner.run(
            orchestrator_agent, 
            user_query, 
            context=agent_run_context,
            max_turns=20  
        )
        
        print("\nWorkflow completed!")
        if run_outcome:
            print(f"Final outcome: {run_outcome}")

    except Exception as e:
        logging.error("An error occurred during the workflow execution:", exc_info=True)
        print(f"ERROR: {e}")

    print(f"\nResults saved in: {BASE_EXECUTION_DIR}/")
    print("- exploit_analysis/ - Security analysis results")
    print("- approved_fixes/ - Final approved fixes")

if __name__ == "__main__":
    asyncio.run(main())
