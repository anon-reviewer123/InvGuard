// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleBank {
    address public owner;
    mapping(address => uint256) public balances;

    constructor() {
        owner = msg.sender;
    }

    function deposit() public payable {
        require(msg.value > 0, "Deposit must be greater than zero");
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        // ⚠️ Vulnerable to re-entrancy: state update happens after external call
        balances[msg.sender] -= amount;
        payable(msg.sender).transfer(amount);
    }
}
