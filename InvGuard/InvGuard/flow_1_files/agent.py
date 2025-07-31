import asyncio
import os
import logging
import sys
from dataclasses import dataclass, field
from tools import*
from typing import Dict, List, Any
import json
from agents import Agent, Runner, function_tool, handoff
from openai import OpenAI
from z3_checker import Z3Checker
from invariant_autogen import generate_invariants
from dataclasses import dataclass, field

os.environ["OPENAI_API_KEY"] = "<your-api-key>" 


client = OpenAI()
model_1 = "<your-fine-tuned-model>"
model_2 = "<model-name>"

BASE_EXECUTION_DIR = "<add-base-execution-dir>"
CORRECT_INVARIANTS_DIR = "<add-correct-invariants-dir>"
MAX_REFINEMENT_ITERATIONS = "<can-be-customised>"

@dataclass
class Z3CheckerResult:
    """Result structure for Z3 checker analysis"""
    verified_invariants: List[str] = field(default_factory=list)
    failed_invariants: List[Dict[str, Any]] = field(default_factory=list)
    trusted_invariants: List[str] = field(default_factory=list)
    report: str = ""

@dataclass
class AgentContext:
    user_query: str
    generated_invariants: list[str] = field(default_factory=list)
    z3_results: Z3CheckerResult = field(default_factory=Z3CheckerResult)
    refinement_iteration: int = 0
    failed_invariants_for_refinement: List[Dict[str, Any]] = field(default_factory=list)

@function_tool
def z3_checker_tool(contract_filename: str = "contract.sol", invariants_filename: str = "invariants.txt") -> Z3CheckerResult:
    """
    Run Z3 verification on smart contract invariants and categorize results.
    
    Args:
        contract_filename: Name of the .sol file in the base execution directory
        invariants_filename: Name of the .txt file containing invariants
    
    Returns:
        Z3CheckerResult containing categorized invariants and analysis report
    """
    print("Starting Solidity Invariant Validator...")
    
    
    contract_file = os.path.join(BASE_EXECUTION_DIR, contract_filename)
    invariant_txt_file = os.path.join(BASE_EXECUTION_DIR, invariants_filename)
    invariant_json_file = os.path.join(BASE_EXECUTION_DIR, "invariants.json")
    report_file = os.path.join(BASE_EXECUTION_DIR, "z3_validation_report.txt")
    
    result = Z3CheckerResult()
    
    print(f"Using contract: {contract_file}")
    print(f"Reading expressions from: {invariant_txt_file}")
    
    
    try:
        raw_exprs = load_invariants_from_file(invariant_txt_file)
        if not raw_exprs:
            result.report = "No invariants found in the file"
            return result
    except Exception as e:
        result.report = f"Failed to read invariants.txt: {e}"
        return result
    
    
    try:
        invariants = generate_invariants(contract_file, raw_exprs)
        save_invariants_json(invariants, invariant_json_file)
        print(f"Generated and saved invariants.json")
    except Exception as e:
        result.report = f"Error generating invariants: {e}"
        return result
    
    
    checker = Z3Checker()
    validation_results = []
    report_lines = []
    
    print("\nValidating invariants...\n")
    
    for idx, inv in enumerate(invariants, 1):
        expr = inv["expr"]
        var_defs = inv["vars"]
        original_invariant = raw_exprs[idx-1] if idx <= len(raw_exprs) else expr
        
        if inv.get("trusted", False):
            result.trusted_invariants.append(original_invariant)
            validation_results.append({
                "status": "TRUSTED (skipped)",
                "model": None
            })
            report_line = f"Invariant {idx}: TRUSTED (skipped)"
            print(report_line)
            report_lines.append(report_line)
            continue
        
        try:
            always_true, counterexample = checker.is_always_true(expr, var_defs)
            
            if always_true:
                result.verified_invariants.append(original_invariant)
                validation_results.append({
                    "status": "ALWAYS HOLDS",
                    "model": None
                })
                report_line = f"Invariant {idx}: ALWAYS HOLDS"
                print(report_line)
                report_lines.append(report_line)
            else:
                result.failed_invariants.append({
                    "invariant": original_invariant,
                    "counterexample": str(counterexample) if counterexample else "No counterexample provided"
                })
                validation_results.append({
                    "status": "CAN FAIL",
                    "model": str(counterexample) if counterexample else None
                })
                report_line = f"Invariant {idx}: CAN FAIL"
                if counterexample:
                    report_line += f"\n  Counterexample: {counterexample}"
                print(report_line)
                report_lines.append(report_line)
                
        except Exception as e:
            error_msg = f"Error checking invariant {idx}: {e}"
            # print(error_msg)
            report_lines.append(error_msg)
            
            result.trusted_invariants.append(original_invariant)
            validation_results.append({
                "status": "TRUSTED",
                "model": None
            })
            trusted_line = f"Invariant {idx}: TRUSTED"
            print(trusted_line)
            report_lines.append(trusted_line)
    
    
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    write_report(validation_results, report_file)
    
    
    save_verified_invariants(result.verified_invariants, result.trusted_invariants)
    
    result.report = "\n".join(report_lines)
    
    print(f"\nValidation report saved to: {report_file}")
    print(f"Verified invariants (ALWAYS HOLDS): {len(result.verified_invariants)}")
    print(f"Failed invariants: {len(result.failed_invariants)}")
    print(f"Trusted invariants: {len(result.trusted_invariants)}")
    print(f"Total saved to verified file: {len(result.verified_invariants) + len(result.trusted_invariants)}")
    
    return result

def load_invariants_from_file(file_path: str) -> List[str]:
    """Load invariant expressions from text file"""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Invariant file not found: {file_path}")
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def write_report(results: List[Dict], output_path: str):
    """Write results to report.txt"""
    with open(output_path, 'w') as f:
        for i, res in enumerate(results, 1):
            f.write(f"Invariant {i}: {res['status']}\n")
            if res['status'] == "CAN FAIL" and res['model']:
                f.write(f"  Counterexample: {res['model']}\n")
            f.write("\n")

def save_invariants_json(invariants: List[Dict], output_path: str):
    """Save the autogenerated invariants.json for debugging"""
    with open(output_path, 'w') as f:
        json.dump(invariants, f, indent=2)

def save_verified_invariants(verified_invariants: List[str], trusted_invariants: List[str]):
    """Save verified invariants (ALWAYS HOLDS + TRUSTED) to the correct directory"""
    if trusted_invariants is None:
        trusted_invariants = []
        
    try:
        clean_dir = CORRECT_INVARIANTS_DIR.strip()
        os.makedirs(clean_dir, exist_ok=True)
        print(f"    Created/verified directory: {clean_dir}")
        
        verified_file = os.path.join(clean_dir, "verified_invariants.txt")
        
        with open(verified_file, 'w') as f:
            total_saved = 0
            
            
            if verified_invariants:
                f.write("# ALWAYS HOLDS - Formally verified invariants\n")
                for invariant in verified_invariants:
                    f.write(f"{invariant}\n")
                    total_saved += 1
                f.write("\n")
            
            if trusted_invariants:
                f.write("# TRUSTED - Invariants that couldn't be formally verified but are considered valid\n")
                for invariant in trusted_invariants:
                    f.write(f"{invariant}\n")
                    total_saved += 1
                f.write("\n")
            
            if total_saved > 0:
                print(f"{len(verified_invariants)} ALWAYS HOLDS invariants saved")
                print(f"{len(trusted_invariants)} TRUSTED invariants saved")
                print(f"Total {total_saved} verified invariants saved to: {verified_file}")
            else:
                f.write("# No verified invariants found\n")
                print(f"No verified invariants to save. Empty file created at: {verified_file}")
                
    except Exception as e:
        print(f"Error saving verified invariants: {e}")
        print(f"Attempted directory: {CORRECT_INVARIANTS_DIR}")
        try:
            fallback_dir = os.path.join(BASE_EXECUTION_DIR, "verified_invariants_fallback")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback_file = os.path.join(fallback_dir, "verified_invariants.txt")
            with open(fallback_file, 'w') as f:
                total_saved = 0
                
                if verified_invariants:
                    f.write("# ALWAYS HOLDS - Formally verified invariants\n")
                    for invariant in verified_invariants:
                        f.write(f"{invariant}\n")
                        total_saved += 1
                    f.write("\n")
                
                if trusted_invariants:
                    f.write("# TRUSTED - Invariants that couldn't be formally verified but are considered valid\n")
                    for invariant in trusted_invariants:
                        f.write(f"{invariant}\n")
                        total_saved += 1
                    f.write("\n")
                
                if total_saved == 0:
                    f.write("# No verified invariants found\n")
                    
            print(f"Fallback: Saved to {fallback_file}")
        except Exception as fallback_error:
            print(f"Fallback also failed: {fallback_error}")


z3_checker_agent = Agent[AgentContext](
    name="z3_checker_agent",
    instructions="""
You are an expert smart contract verification specialist using Z3 theorem prover to validate invariants.

Your primary responsibilities:
1. Run the z3_checker_tool to analyze smart contracts and validate invariants
2. Process verification results and categorize invariants
3. Provide detailed feedback on failed invariants with counterexamples
4. Decide whether to hand off failed invariants back to the invariant generator for refinement

VERIFICATION PROCESS:
1. Use the z3_checker_tool to load the smart contract (.sol file) and invariants (.txt file)
2. The tool will automatically run Z3 formal verification on each invariant
3. Review the results and categorize:
   - VERIFIED: Invariants that always hold (proven correct)
   - FAILED: Invariants that can be violated (with counterexamples)
   - TRUSTED: Invariants that couldn't be checked due to parsing/complexity issues

DECISION LOGIC FOR FAILED INVARIANTS:
- If there are failed invariants AND refinement_iteration < MAX_REFINEMENT_ITERATIONS:
  * Store failed invariants in context.failed_invariants_for_refinement
  * Hand off to invariant_refiner_agent for refinement
- If refinement_iteration >= MAX_REFINEMENT_ITERATIONS:
  * Accept the current results and finish
  * Report that maximum refinement attempts reached

OUTPUT REQUIREMENTS:
- Always call the z3_checker_tool first
- Store z3_results in the context
- Provide a clear summary of verification results
- Highlight any failed invariants and their counterexamples
- Report the total counts of verified, failed, and trusted invariants
- Make handoff decision based on failed invariants and iteration count

The tool will automatically save verified invariants to the appropriate directory.
""",
    model=model_2,
    tools=[z3_checker_tool],
    handoffs=[]  
)


invariant_refiner_agent = Agent[AgentContext](
    name="invariant_refiner_agent",
    instructions="""
You are an expert smart contract security analyst specializing in refining failed invariants based on counterexamples.

Your primary responsibilities:
1. Analyze failed invariants and their counterexamples from Z3 verification
2. Generate improved/corrected invariants that address the specific failure cases
3. Save the refined invariants and hand back to Z3 checker for re-verification

REFINEMENT PROCESS:
1. Receive failed invariants with counterexamples from the context
2. Analyze each failed invariant and its counterexample to understand why it failed
3. Generate refined versions that:
   - Address the specific counterexample scenario
   - Maintain the original security intent
   - Are more precise and accurate
4. Save the refined invariants using save_invariants()
5. Increment refinement_iteration in context
6. Hand off to z3_checker_agent for re-verification

REFINEMENT STRATEGIES:
- Add boundary conditions to handle edge cases revealed by counterexamples
- Strengthen preconditions where invariants are too weak
- Add exception cases for legitimate scenarios shown in counterexamples
- Split complex invariants into simpler, more verifiable components
- Add temporal or state-dependent conditions

REFINEMENT GUIDELINES:
- Focus on the specific failure revealed by the counterexample
- Maintain the security property the original invariant was trying to capture
- Generate multiple refined alternatives if appropriate
- Ensure refined invariants are syntactically correct
- Document the refinement reason as a comment (internally, not in the invariant file)

OUTPUT FORMAT:
- Generate clean, precise refined invariant expressions
- Use standard Solidity syntax and operators
- Each invariant should be a single logical expression
- Avoid explanatory text in the invariant expressions themselves

You MUST always hand off to the Z3 checker agent after generating refined invariants.
""",
    model=model_1,
    tools=[save_invariants],
    handoffs=[]  
)


invariant_generating_agent = Agent[AgentContext](
    name="invariant_generating_agent",
    instructions="""
You are an expert smart contract security analyst specializing in generating comprehensive invariants for Solidity smart contracts.

Your primary responsibilities:
1. Analyze the provided smart contract code thoroughly
2. Generate meaningful invariants that capture important security properties and business logic constraints
3. Save the contract and invariants using the provided tools
4. Hand off to the Z3 checker agent for verification

INVARIANT GENERATION GUIDELINES:
- Focus on critical security properties (overflow/underflow, access control, state consistency)
- Include business logic constraints (balance relationships, ownership rules, state transitions)
- Generate both positive assertions (what should be true) and negative constraints (what should never happen)
- Consider edge cases and potential vulnerabilities
- Ensure invariants are syntactically correct and meaningful

INVARIANT TYPES TO CONSIDER:
- Access control invariants (e.g., only owner can perform certain actions)
- State consistency invariants (e.g., array bounds, contract lifecycle)
- Mathematical constraints (e.g., no negative values where inappropriate)
- Ownership and permission invariants
- Data structure integrity (e.g., map bounds, array consistency)
- Balance and accounting invariants

OUTPUT FORMAT:
- Invariants must be Z3-compatible expressions using Python-style syntax
- Use logical expressions like:
    - `balances[msg_sender] >= 0`
    - `Implies(msg_value > 0, balances[msg_sender] == balances[msg_sender] + msg_value)`
- Use `Implies(cond, consequence)` for implications instead of `->`
- Replace Solidity identifiers:
    - `msg.sender` → `msg_sender`
    - `msg.value` → `msg_value`
    - `getBalance()` → `balances[msg_sender]` (if relevant)
- Avoid assignment or mutation syntax like `+=`, `-=`, or function calls like `transfer(...)`
- Avoid informal words like "before", "after", "should", or "must"
- Each invariant must be a self-contained logical assertion, not a code instruction
- Do NOT include explanatory comments or natural language in the expressions

PROCESS:
1. First, save the smart contract using save_contract()
2. Analyze the contract to identify key state variables, functions, and potential vulnerabilities
3. Generate all meaningful invariants (no limit on quantity)
4. Save the invariants using save_invariants()
5. Provide a brief summary of the types of invariants generated
6. **MANDATORY**: Hand off to the Z3 checker agent using z3_checker_agent_handoff

You MUST always hand off to the Z3 checker agent after generating and saving invariants.
""",
    model=model_1,
    tools=[save_contract, save_invariants],
    handoffs=[]  
)


orchestrator_agent = Agent[AgentContext](
    name="orchestrator_agent",
    instructions="""You are the Orchestrator Agent for smart contract invariant generation with refinement feedback loop.

Your role is simple:
1. Receive the user query containing a smart contract
2. Hand off to the Invariant Generating Agent to analyze the contract and generate invariants
3. The system will automatically handle the feedback loop:
   - Invariant Generator → Z3 Checker → (if failed invariants) → Invariant Refiner → Z3 Checker
   - This continues until all invariants pass or maximum refinement iterations are reached

Simply call the `invariant_generating_agent_handoff` tool with the user's query.
""",
    model=model_2,
    tools=[],
    handoffs=[]
)


z3_checker_agent_handoff = handoff(
    agent=z3_checker_agent,
    tool_name_override="z3_checker_agent_handoff",
    tool_description_override="Hands off to the Z3 Checker Agent to verify generated invariants using formal verification.",
)

invariant_refiner_agent_handoff = handoff(
    agent=invariant_refiner_agent,
    tool_name_override="invariant_refiner_agent_handoff",
    tool_description_override="Hands off to the Invariant Refiner Agent to improve failed invariants based on counterexamples.",
)

invariant_generating_agent_handoff = handoff(
    agent=invariant_generating_agent,
    tool_name_override="invariant_generating_agent_handoff",
    tool_description_override="Hands off to the Invariant Generating Agent to analyze the smart contract and generate invariants.",
)


z3_checker_agent.handoffs = [invariant_refiner_agent_handoff]
invariant_refiner_agent.handoffs = [z3_checker_agent_handoff]
invariant_generating_agent.handoffs = [z3_checker_agent_handoff]
orchestrator_agent.handoffs = [invariant_generating_agent_handoff]

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    user_query = """
Please analyze the following Solidity smart contract and generate invariants for it:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleBank {
    address public owner;
    mapping(address => uint256) public balances;

    constructor() {
        owner = msg.sender;
    }

    function deposit() public payable {
        require(msg.value > 0, "Must deposit positive amount");
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        balances[msg.sender] -= amount;
        payable(msg.sender).transfer(amount);
    }

    function getBalance() public view returns (uint256) {
        return balances[msg.sender];
    }

    function kill() public {
        require(msg.sender == owner, "Only owner can destroy");
        selfdestruct(payable(owner));
    }
}
"""

    print("Starting smart contract invariant generation workflow with refinement feedback loop...")
    os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
    print(f"Execution artifacts will be saved in: {BASE_EXECUTION_DIR}/")
    print(f"Maximum refinement iterations: {MAX_REFINEMENT_ITERATIONS}")

    agent_run_context = AgentContext(user_query=user_query)

    try:
        run_outcome = await Runner.run(
            orchestrator_agent, 
            user_query, 
            context=agent_run_context,
            max_turns=20 
        )
        
        print("\nWorkflow completed successfully!")
        print(f"Final refinement iteration: {agent_run_context.refinement_iteration}")
        if run_outcome:
            print(f"Final outcome: {run_outcome}")
        else:
            print("Invariant generation and verification completed. Check the output directory for results.")

    except Exception as e:
        logging.error("An error occurred during the workflow execution:", exc_info=True)
        print(f"ERROR: An unhandled exception occurred: {e}")
        print(f"Please check the logs and the '{BASE_EXECUTION_DIR}' directory for more details.")

    print(f"\nResults saved in: {BASE_EXECUTION_DIR}/")
    print("- contract.sol - The analyzed smart contract")
    print("- invariants.txt - Final generated invariants")
    print("- z3_validation_report.txt - Verification results")
    print(f"- {CORRECT_INVARIANTS_DIR}/ - Verified invariants")

if __name__ == "__main__":
    asyncio.run(main())
