// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract BranchyToken {
    mapping(address => uint256) public balances;
    uint256 public totalSupply;

    constructor(uint256 init) {
        balances[msg.sender] = init;
        totalSupply = init;
    }

    // If x > 10, add x to totalSupply; else, subtract x.
    function tweak(uint256 x) public {
        if (x > 10) {
            totalSupply += x;
        } else {
            totalSupply -= x;
        }
    }
}

