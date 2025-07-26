pragma solidity ^0.4.19;

interface ITarget {
    function run(uint256 input) external;
}

contract ExploitBenign {
    function attack(address targetAddr) public {
        ITarget(targetAddr).run(100); // trigger underflow: 1 - 100 => large uint
        // No effect on target state
    }
}

