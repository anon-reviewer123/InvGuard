
from agents import function_tool 

import os
import time
import tempfile
import subprocess
from typing import List
from pathlib import Path
BASE_EXECUTION_DIR = "<add-base-execution-dir>"
@function_tool
def save_contract(contract_code: str, filename: str = "contract.sol") -> str:
    """
    Save smart contract code to a .sol file in the base execution directory.
    
    Args:
        contract_code: The Solidity smart contract code to save
        filename: Name of the .sol file (default: contract.sol)
    
    Returns:
        String confirmation of file saved with full path
    """

    os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
    
    
    if not filename.endswith('.sol'):
        filename += '.sol'
    
    file_path = os.path.join(BASE_EXECUTION_DIR, filename)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(contract_code)
        return f"Smart contract successfully saved to: {file_path}"
    except Exception as e:
        return f"Error saving contract: {str(e)}"

@function_tool
def save_invariants(invariants: List[str], filename: str = "invariants.txt") -> str:
    """
    Save generated invariants to a .txt file in the base execution directory.
    Only saves the invariant expressions, one per line.
    
    Args:
        invariants: List of invariant expressions
        filename: Name of the .txt file (default: invariants.txt)
    
    Returns:
        String confirmation of file saved with full path
    """
    
    os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
    
    
    if not filename.endswith('.txt'):
        filename += '.txt'
    
    file_path = os.path.join(BASE_EXECUTION_DIR, filename)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for invariant in invariants:
                
                clean_invariant = invariant.strip()
                f.write(f"{clean_invariant}\n")
        return f"Invariants successfully saved to: {file_path}"
    except Exception as e:
        return f"Error saving invariants: {str(e)}"

