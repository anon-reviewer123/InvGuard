// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Minimal, intentionally buggy token for invariant testing.
// BUG: transfer() forgets to decrement the sender's balance.

contract BadToken {
    mapping(address => uint256) public balances;
    uint256 public totalSupply;

    constructor(uint256 _initialSupply) {
        balances[msg.sender] = _initialSupply;
        totalSupply = _initialSupply;
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        require(balances[msg.sender] >= amount, "Not enough balance");
        // BUG: missing balances[msg.sender] -= amount;
        balances[to] += amount;
        return true;
    }

    // Mint and burn are correct here to isolate the transfer bug,
    // but you can also test invariants on these if you want.
    function mint(uint256 amount) public {
        balances[msg.sender] += amount;
        totalSupply += amount;
    }

    function burn(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Not enough balance");
        balances[msg.sender] -= amount;
        totalSupply -= amount;
    }
}

